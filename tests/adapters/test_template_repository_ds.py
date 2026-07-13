"""Persistence behavior for template versions."""

from pathlib import Path

from app.adapters.database.models import Base
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.domain.templates_ds import (
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateArtifact,
    TemplateVersion,
)
from app.infrastructure.database.sqlite_ds import create_sqlite_engine


def test_repository_round_trips_fields_and_safe_artifact_metadata(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "template.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    version.add_field(
        FieldDefinition(
            "worker_name",
            "姓名",
            "text",
            "text_box",
            Rect(0.1, 0.1, 0.2, 0.05),
            version.page,
        )
    )
    version.add_field(
        FieldDefinition(
            "hours",
            "工时",
            "decimal",
            "digit_boxes",
            Rect(0.1, 0.2, 0.2, 0.05),
            version.page,
        )
    )

    repository.add_version(version)
    repository.add_artifact(
        TemplateArtifact(
            "ART-1",
            version.version_id,
            "PRINT_PDF",
            "PAYROLL_HOURLY-v1.pdf",
            "evidence://templates/ART-1.pdf",
            "a" * 64,
        )
    )

    loaded = repository.get_version(version.version_id)

    assert loaded is not None
    assert loaded.template_key == "PAYROLL_HOURLY"
    assert [field.field_key for field in loaded.fields] == ["worker_name", "hours"]
    artifact = repository.list_artifacts(version.version_id)[0]
    assert artifact.download_name == "PAYROLL_HOURLY-v1.pdf"
    assert artifact.sha256 == "a" * 64

    loaded.mark_ready_to_publish()
    repository.replace_version(loaded)

    assert repository.get_version(version.version_id).status.value == "READY_TO_PUBLISH"  # type: ignore[union-attr]
    assert repository.list_versions("PAYROLL_HOURLY")[0].version_id == version.version_id


def test_repository_lists_distinct_template_keys_in_lexical_order(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "template.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyTemplateRepository(engine)
    page = PageSpec.a4_portrait()

    repository.add_version(TemplateVersion.draft("TPL-H-1", "PAYROLL_HOURLY", 1, page))
    repository.add_version(TemplateVersion.draft("TPL-H-2", "PAYROLL_HOURLY", 2, page))
    repository.add_version(
        TemplateVersion.draft("TPL-P-1", "PAYROLL_STANDARD_PIECE", 1, page)
    )

    assert repository.list_template_keys() == ["PAYROLL_HOURLY", "PAYROLL_STANDARD_PIECE"]
