"""Construct application services from runtime settings."""

from dataclasses import dataclass

from sqlalchemy import Engine

from app.adapters.ai.disabled import DisabledAIReview
from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.export.xlsx import XlsxExporter
from app.adapters.recognition.opencv import OpenCvImagePipeline
from app.adapters.storage.local import LocalEvidenceStorage
from app.adapters.vector.local import LocalVectorIndex
from app.application.ai_review_forms import AIReviewForms
from app.application.export_forms import ExportForms
from app.application.import_forms import ImportForms
from app.application.query_forms import QueryForms
from app.application.recognize_forms import RecognizeForms
from app.application.review_forms import ReviewForms
from app.infrastructure.database.sqlite import create_sqlite_engine
from app.infrastructure.database.uow import SqlAlchemyUnitOfWork
from app.infrastructure.tasks.sqlite_store import SqliteTaskStore
from app.modules.review.facade import ReviewFacade
from app.modules.review.lease_service import ReviewLeaseService
from app.modules.review.repository import SqlAlchemyReviewLeaseRepository
from app.modules.tasks.service import TaskService
from config.settings import Settings


@dataclass(frozen=True, slots=True)
class Services:
    settings: Settings
    engine: Engine
    repository: SqlAlchemyFormRepository
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
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    storage = LocalEvidenceStorage(settings.evidence_root)
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
        imports=ImportForms(repository, repository, repository, storage),
        reviews=ReviewForms(repository, repository),
        queries=queries,
        exports=ExportForms(repository, XlsxExporter(), queries),
        recognition=RecognizeForms(repository, repository, repository, storage, pipeline),
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
