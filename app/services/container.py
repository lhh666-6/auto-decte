"""Construct application services from runtime settings."""

from dataclasses import dataclass

from sqlalchemy import create_engine

from app.adapters.ai.disabled import DisabledAIReview
from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.export.xlsx import XlsxExporter
from app.adapters.storage.local import LocalEvidenceStorage
from app.adapters.vector.local import LocalVectorIndex
from app.application.ai_review_forms import AIReviewForms
from app.application.export_forms import ExportForms
from app.application.import_forms import ImportForms
from app.application.query_forms import QueryForms
from app.application.review_forms import ReviewForms
from config.settings import Settings


@dataclass(frozen=True, slots=True)
class Services:
    settings: Settings
    repository: SqlAlchemyFormRepository
    imports: ImportForms
    reviews: ReviewForms
    queries: QueryForms
    exports: ExportForms
    ai_reviews: AIReviewForms
    vector_index: LocalVectorIndex


def build_services(settings: Settings) -> Services:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{settings.database_path}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    storage = LocalEvidenceStorage(settings.evidence_root)
    queries = QueryForms(repository)
    return Services(
        settings=settings,
        repository=repository,
        imports=ImportForms(repository, repository, repository, storage),
        reviews=ReviewForms(repository, repository),
        queries=queries,
        exports=ExportForms(repository, XlsxExporter(), queries),
        ai_reviews=AIReviewForms(repository, repository, DisabledAIReview()),
        vector_index=LocalVectorIndex(),
    )
