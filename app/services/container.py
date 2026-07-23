"""Construct application services from runtime settings."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine

from app.adapters.ai.deepseek_ds import DeepSeekCompletion
from app.adapters.ai.disabled import DisabledAIReview
from app.adapters.ai.report_assistant_ds import (
    DisabledReportAssistant,
    StructuredReportAssistantProvider,
)
from app.adapters.database.bamboo_process_repository_ds import (
    SqlAlchemyBambooProcessRepository,
    install_default_bamboo_payroll_rules,
)
from app.adapters.database.electronic_definition_repository_ds import (
    SqlAlchemyElectronicDefinitionRepository,
)
from app.adapters.database.fact_record_repository_ds import (
    SqlAlchemyFactRecordRepository,
)
from app.adapters.database.mobile_identity_repository_ds import (
    SqlAlchemyMobileIdentityRepository,
)
from app.adapters.database.models import Base
from app.adapters.database.report_definition_repository_ds import (
    SqlAlchemyReportDefinitionRepository,
    install_builtin_report_definitions,
)
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.adapters.export.xlsx import XlsxExporter
from app.adapters.recognition.opencv import OpenCvImagePipeline
from app.adapters.storage.local import LocalEvidenceStorage
from app.adapters.templates.print_renderer_ds import TemplatePrintRenderer
from app.adapters.vector.local import LocalVectorIndex
from app.application.ai_review_forms import AIReviewForms
from app.application.bamboo_operations_ds import BambooOperationsService
from app.application.electronic_submissions_ds import ElectronicFormIntegration
from app.application.export_forms import ExportForms
from app.application.import_forms import ImportForms
from app.application.job_profiles_ds import JobProfiles
from app.application.mobile_identity_ds import MobileIdentityService
from app.application.query_forms import QueryForms
from app.application.recognize_forms import RecognizeForms
from app.application.report_assistant_ds import ReportAssistant
from app.application.review_forms import ReviewForms
from app.application.template_versions_ds import TemplateVersions
from app.infrastructure.database.electronic_submission_uow_ds import (
    SqlAlchemyElectronicSubmissionUnitOfWork,
)
from app.infrastructure.database.migrations import (
    ensure_auto_created_schema_compatibility,
    is_alembic_managed,
    upgrade_database,
    verify_database_revision,
)
from app.infrastructure.database.sqlite_ds import create_sqlite_engine
from app.infrastructure.database.uow_ds import SqlAlchemyUnitOfWork
from app.infrastructure.tasks.sqlite_store_ds import SqliteTaskStore
from app.modules.bamboo_process.facade_ds import BambooProcessFacade
from app.modules.electronic_forms.facade_ds import ElectronicDefinitionService
from app.modules.fact_records.facade_ds import FactRecordFacade
from app.modules.master_data.facade_ds import MasterDataFacade
from app.modules.master_data.repository_ds import SqlAlchemyMasterDataRepository
from app.modules.reporting.facade_ds import ReportingFacade
from app.modules.reporting.handler_ds import ExportHandler
from app.modules.review.facade_ds import ReviewFacade
from app.modules.review.lease_service_ds import ReviewLeaseService
from app.modules.review.repository_ds import SqlAlchemyReviewLeaseRepository
from app.modules.tasks.service_ds import TaskService
from app.modules.templates.core_payroll_layouts_ds import (
    install_reviewed_job_profile_seeds,
)
from app.modules.templates.seed_templates_ds import (
    SeedTemplateConflict,
    install_legacy_payroll_seed_templates,
)
from config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Services:
    settings: Settings
    engine: Engine
    repository: SqlAlchemyFormRepository
    template_repository: SqlAlchemyTemplateRepository
    report_definition_repository: SqlAlchemyReportDefinitionRepository
    templates: TemplateVersions
    job_profiles: JobProfiles
    template_renderer: TemplatePrintRenderer
    imports: ImportForms
    reviews: ReviewForms
    queries: QueryForms
    exports: ExportForms
    reporting: ReportingFacade
    export_handler: ExportHandler
    recognition: RecognizeForms
    ai_reviews: AIReviewForms
    report_assistant: ReportAssistant
    vector_index: LocalVectorIndex
    review_leases: ReviewLeaseService
    review_repository: SqlAlchemyReviewLeaseRepository
    review_facade: ReviewFacade
    task_store: SqliteTaskStore
    tasks: TaskService
    evidence_storage: LocalEvidenceStorage
    master_data_repository: SqlAlchemyMasterDataRepository
    master_data: MasterDataFacade
    fact_record_repository: SqlAlchemyFactRecordRepository
    fact_records: FactRecordFacade
    electronic_integration: ElectronicFormIntegration
    mobile_identity_repository: SqlAlchemyMobileIdentityRepository
    mobile_identity: MobileIdentityService
    electronic_definition_repository: SqlAlchemyElectronicDefinitionRepository
    electronic_definitions: ElectronicDefinitionService
    bamboo_repository: SqlAlchemyBambooProcessRepository
    bamboo_process: BambooProcessFacade
    bamboo_operations: BambooOperationsService


def build_services(settings: Settings, *, install_seed_templates: bool = False) -> Services:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_sqlite_engine(settings.database_path)
    if settings.auto_create_schema:
        if is_alembic_managed(engine):
            engine.dispose()
            upgrade_database(settings.database_path)
            engine = create_sqlite_engine(settings.database_path)
        else:
            ensure_auto_created_schema_compatibility(engine)
            Base.metadata.create_all(engine)
            ensure_auto_created_schema_compatibility(engine)
    else:
        verify_database_revision(engine)
    repository = SqlAlchemyFormRepository(engine)
    template_repository = SqlAlchemyTemplateRepository(engine)
    report_definition_repository = SqlAlchemyReportDefinitionRepository(engine)
    install_builtin_report_definitions(report_definition_repository)
    storage = LocalEvidenceStorage(settings.evidence_root)
    font_candidates = (settings.cjk_font_path,) if settings.cjk_font_path is not None else None
    template_renderer = TemplatePrintRenderer(
        settings.evidence_root,
        font_candidates=font_candidates,
    )
    queries = QueryForms(repository)
    pipeline = OpenCvImagePipeline()
    review_repository = SqlAlchemyReviewLeaseRepository(engine)
    master_data_repository = SqlAlchemyMasterDataRepository(engine)
    master_data = MasterDataFacade(master_data_repository)
    fact_record_repository = SqlAlchemyFactRecordRepository(engine)
    fact_records = FactRecordFacade(fact_record_repository)
    electronic_integration = ElectronicFormIntegration(
        uow_factory=lambda: SqlAlchemyElectronicSubmissionUnitOfWork(engine),
    )
    mobile_identity_repository = SqlAlchemyMobileIdentityRepository(engine)
    mobile_identity = MobileIdentityService(repository=mobile_identity_repository)
    electronic_definition_repository = SqlAlchemyElectronicDefinitionRepository(engine)
    electronic_definitions = ElectronicDefinitionService(electronic_definition_repository)
    bamboo_repository = SqlAlchemyBambooProcessRepository(
        engine,
        plant_audit_wait_hours=settings.bamboo_plant_audit_wait_hours,
    )
    install_default_bamboo_payroll_rules(engine)
    bamboo_process = BambooProcessFacade(
        bamboo_repository,
        clock=lambda: datetime.now(UTC),
        id_factory=lambda: str(uuid4()),
    )
    review_leases = ReviewLeaseService(
        review_repository,
        ttl_seconds=settings.review_lease_seconds,
        audits=repository,
    )
    task_store = SqliteTaskStore(engine)
    tasks = TaskService(task_store)
    exporter = XlsxExporter()
    exports = ExportForms(
        repository,
        exporter,
        queries,
        template_repository=template_repository,
        report_definition_repository=report_definition_repository,
    )
    reporting = ReportingFacade(
        repository,
        queries,
        exporter=exporter,
        template_repository=template_repository,
        report_definition_repository=report_definition_repository,
    )
    services = Services(
        settings=settings,
        engine=engine,
        repository=repository,
        template_repository=template_repository,
        report_definition_repository=report_definition_repository,
        templates=TemplateVersions(template_repository),
        job_profiles=JobProfiles(template_repository, template_repository),
        template_renderer=template_renderer,
        imports=ImportForms(repository, repository, repository, storage),
        reviews=ReviewForms(repository, repository),
        queries=queries,
        exports=exports,
        reporting=reporting,
        export_handler=ExportHandler(
            exports,
            tasks,
            repository,
            settings.exports_root,
        ),
        recognition=RecognizeForms(
            repository,
            repository,
            repository,
            storage,
            pipeline,
            template_repository,
        ),
        ai_reviews=AIReviewForms(repository, repository, DisabledAIReview()),
        report_assistant=ReportAssistant(
            report_definition_repository,
            (
                StructuredReportAssistantProvider(
                    DeepSeekCompletion(
                        settings.deepseek_api_key,
                        settings.deepseek_endpoint,
                        settings.deepseek_model,
                        settings.deepseek_timeout_seconds,
                    )
                )
                if settings.ai_enabled and settings.deepseek_api_key
                else DisabledReportAssistant()
            ),
        ),
        vector_index=LocalVectorIndex(),
        review_leases=review_leases,
        review_repository=review_repository,
        review_facade=ReviewFacade(
            uow_factory=lambda: SqlAlchemyUnitOfWork(engine),
            leases=review_leases,
            template_versions=template_repository,
            master_data=master_data,
            lease_ttl_seconds=settings.review_lease_seconds,
        ),
        task_store=task_store,
        tasks=tasks,
        evidence_storage=storage,
        master_data_repository=master_data_repository,
        master_data=master_data,
        fact_record_repository=fact_record_repository,
        fact_records=fact_records,
        electronic_integration=electronic_integration,
        mobile_identity_repository=mobile_identity_repository,
        mobile_identity=mobile_identity,
        electronic_definition_repository=electronic_definition_repository,
        electronic_definitions=electronic_definitions,
        bamboo_repository=bamboo_repository,
        bamboo_process=bamboo_process,
        bamboo_operations=BambooOperationsService(engine, storage),
    )
    # Legacy recognition/export tasks are no longer started by the Web mainline.
    if install_seed_templates:
        try:
            install_legacy_payroll_seed_templates(template_repository, template_renderer)
            install_reviewed_job_profile_seeds(template_repository)
        except SeedTemplateConflict as error:
            logger.warning("Built-in template installation skipped: %s", error)
    return services
