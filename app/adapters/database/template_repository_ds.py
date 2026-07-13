"""SQLAlchemy persistence adapter for immutable template versions."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    TemplateArtifactRow,
    TemplateFieldRow,
    TemplateVersionRow,
)
from app.domain.templates_ds import (
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateArtifact,
    TemplateStatus,
    TemplateVersion,
)


class SqlAlchemyTemplateRepository:
    """Store template metadata separately from imported form facts."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        with Session(self._engine) as session, session.begin():
            yield session

    @contextmanager
    def _read_session(self) -> Iterator[Session]:
        with Session(self._engine) as session:
            yield session

    def add_version(self, version: TemplateVersion) -> None:
        with self._transaction() as session:
            session.add(
                TemplateVersionRow(
                    version_id=version.version_id,
                    template_key=version.template_key,
                    version=version.version,
                    status=version.status.value,
                    page=_page_to_dict(version.page),
                    parent_version_id=version.parent_version_id,
                )
            )
            session.flush()
            for position, definition in enumerate(version.fields):
                session.add(
                    TemplateFieldRow(
                        field_id=f"{version.version_id}:{definition.field_key}",
                        version_id=version.version_id,
                        field_key=definition.field_key,
                        position=position,
                        definition=_field_to_dict(definition),
                    )
                )

    def get_version(self, version_id: str) -> TemplateVersion | None:
        with self._read_session() as session:
            row = session.get(TemplateVersionRow, version_id)
            if row is None:
                return None
            fields = session.scalars(
                select(TemplateFieldRow)
                .where(TemplateFieldRow.version_id == version_id)
                .order_by(TemplateFieldRow.position, TemplateFieldRow.field_id)
            ).all()
            page = _page_from_dict(row.page)
            return TemplateVersion(
                version_id=row.version_id,
                template_key=row.template_key,
                version=row.version,
                page=page,
                status=TemplateStatus(row.status),
                fields=[_field_from_dict(item.field_key, item.definition, page) for item in fields],
                parent_version_id=row.parent_version_id,
            )

    def add_artifact(self, artifact: TemplateArtifact) -> None:
        with self._transaction() as session:
            session.add(
                TemplateArtifactRow(
                    artifact_id=artifact.artifact_id,
                    version_id=artifact.version_id,
                    kind=artifact.kind,
                    download_name=artifact.download_name,
                    internal_uri=artifact.internal_uri,
                    sha256=artifact.sha256,
                )
            )

    def list_artifacts(self, version_id: str) -> list[TemplateArtifact]:
        with self._read_session() as session:
            rows = session.scalars(
                select(TemplateArtifactRow)
                .where(TemplateArtifactRow.version_id == version_id)
                .order_by(TemplateArtifactRow.artifact_id)
            ).all()
            return [
                TemplateArtifact(
                    artifact_id=row.artifact_id,
                    version_id=row.version_id,
                    kind=row.kind,
                    download_name=row.download_name,
                    internal_uri=row.internal_uri,
                    sha256=row.sha256,
                )
                for row in rows
            ]


def _page_to_dict(page: PageSpec) -> dict[str, object]:
    return {
        "size": page.size,
        "orientation": page.orientation,
        "width_mm": page.width_mm,
        "height_mm": page.height_mm,
        "canonical_dpi": page.canonical_dpi,
        "canonical_width_px": page.canonical_width_px,
        "canonical_height_px": page.canonical_height_px,
    }


def _page_from_dict(value: dict[str, object]) -> PageSpec:
    return PageSpec(
        size=str(value["size"]),
        orientation=str(value["orientation"]),
        width_mm=_as_int(value["width_mm"]),
        height_mm=_as_int(value["height_mm"]),
        canonical_dpi=_as_int(value["canonical_dpi"]),
        canonical_width_px=_as_int(value["canonical_width_px"]),
        canonical_height_px=_as_int(value["canonical_height_px"]),
    )


def _field_to_dict(field: FieldDefinition) -> dict[str, object]:
    return {
        "display_name": field.display_name,
        "data_type": field.data_type,
        "input_type": field.input_type,
        "region": {
            "x": field.region.x,
            "y": field.region.y,
            "width": field.region.width,
            "height": field.region.height,
        },
    }


def _field_from_dict(field_key: str, value: dict[str, object], page: PageSpec) -> FieldDefinition:
    region = value["region"]
    if not isinstance(region, dict):
        raise ValueError("template field region must be an object")
    return FieldDefinition(
        field_key=field_key,
        display_name=str(value["display_name"]),
        data_type=str(value["data_type"]),
        input_type=str(value["input_type"]),
        region=Rect(
            x=float(region["x"]),
            y=float(region["y"]),
            width=float(region["width"]),
            height=float(region["height"]),
        ),
        page=page,
    )


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    raise ValueError("template page dimension must be an integer")
