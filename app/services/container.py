"""Construct application services from runtime settings."""

from dataclasses import dataclass

from sqlalchemy import create_engine

from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.import_forms import ImportForms
from app.application.review_forms import ReviewForms
from config.settings import Settings


@dataclass(frozen=True, slots=True)
class Services:
    repository: SqlAlchemyFormRepository
    imports: ImportForms
    reviews: ReviewForms


def build_services(settings: Settings) -> Services:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{settings.database_path}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    storage = LocalEvidenceStorage(settings.evidence_root)
    return Services(
        repository=repository,
        imports=ImportForms(repository, repository, repository, storage),
        reviews=ReviewForms(repository, repository),
    )
