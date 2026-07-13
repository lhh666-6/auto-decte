"""Construct application services from runtime settings."""

from dataclasses import dataclass

from sqlalchemy import Engine

from app.adapters.ai.disabled import DisabledAIReview
from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.adapters.export.xlsx import XlsxExporter
from app.adapters.recognition.opencv import OpenCvImagePipeline
from app.adapters.storage.local import LocalEvidenceStorage
from app.adapters.templates.print_renderer_ds import TemplatePrintRenderer
from app.adapters.vector.local import LocalVectorIndex
from app.application.ai_review_forms import AIReviewForms
from app.application.export_forms import ExportForms
from app.application.import_forms import ImportForms
from app.application.query_forms import QueryForms
from app.application.recognize_forms import RecognizeForms
from app.application.review_forms import ReviewForms
from app.application.template_versions_ds import TemplateVersions
from app.infrastructure.database.migrations import verify_database_revision
from app.infrastructure.database.sqlite_ds import create_sqlite_engine
from app.infrastructure.database.uow_ds import SqlAlchemyUnitOfWork
from app.infrastructure.tasks.sqlite_store_ds import SqliteTaskStore
from app.modules.review.facade_ds import ReviewFacade
from app.modules.review.lease_service_ds import ReviewLeaseService
from app.modules.review.repository_ds import SqlAlchemyReviewLeaseRepository
from app.modules.tasks.service_ds import TaskService
from config.settings import Settings


@dataclass(frozen=True, slots=True)
class Services:
    settings: Settings
    engine: Engine
    repository: SqlAlchemyFormRepository
    template_repository: SqlAlchemyTemplateRepository
    templates: TemplateVersions
    template_renderer: TemplatePrintRenderer
    imports: ImportForms
    reviews: ReviewForms
    queries: QueryForms
    exports: ExportForms
    recognition: RecognizeForms
    ai_reviews: AIReviewForms
    vector_index: LocalVectorIndex
    review_leases: ReviewLeaseService
    review_facade: ReviewFacade
    task_store: SqliteTaskStore
    tasks: TaskService


def build_services(settings: Settings) -> Services:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_sqlite_engine(settings.database_path)
    if settings.auto_create_schema:
        Base.metadata.create_all(engine)
    else:
        verify_database_revision(engine)
    repository = SqlAlchemyFormRepository(engine)
    template_repository = SqlAlchemyTemplateRepository(engine)
    storage = LocalEvidenceStorage(settings.evidence_root)
    template_renderer = TemplatePrintRenderer(settings.evidence_root)
    queries = QueryForms(repository)
    pipeline = OpenCvImagePipeline()
    review_leases = ReviewLeaseService(
        SqlAlchemyReviewLeaseRepository(engine),
        ttl_seconds=settings.review_lease_seconds,
        audits=repository,
    )
    task_store = SqliteTaskStore(engine)
    return Services(
        settings=settings,
        engine=engine,
        repository=repository,
        template_repository=template_repository,
        templates=TemplateVersions(template_repository),
        template_renderer=template_renderer,
        imports=ImportForms(repository, repository, repository, storage),
        reviews=ReviewForms(repository, repository),
        queries=queries,
        exports=ExportForms(repository, XlsxExporter(), queries),
        recognition=RecognizeForms(
            repository,
            repository,
            repository,
            storage,
            pipeline,
            template_repository,
        ),
        ai_reviews=AIReviewForms(repository, repository, DisabledAIReview()),
        vector_index=LocalVectorIndex(),
        review_leases=review_leases,
        review_facade=ReviewFacade(
            uow_factory=lambda: SqlAlchemyUnitOfWork(engine),
            leases=review_leases,
        ),
        task_store=task_store,
        tasks=TaskService(task_store),
    )
