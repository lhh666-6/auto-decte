"""SQLAlchemy persistence adapter for immutable template versions."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    TemplateArtifactRow,
    TemplateFieldRow,
    TemplateVersionRow,
)
from app.domain.templates_ds import (
    ExportTarget,
    FieldDefinition,
    FieldRules,
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

    def get_version_by_key_version(
        self, template_key: str, version: int
    ) -> TemplateVersion | None:
        """Resolve the immutable version referenced by a paper-form QR or operator."""
        with self._read_session() as session:
            version_id = session.scalar(
                select(TemplateVersionRow.version_id).where(
                    TemplateVersionRow.template_key == template_key,
                    TemplateVersionRow.version == version,
                )
            )
        return self.get_version(version_id) if version_id is not None else None

    def replace_version(self, version: TemplateVersion) -> None:
        with self._transaction() as session:
            row = session.get(TemplateVersionRow, version.version_id)
            if row is None:
                raise KeyError(f"Unknown template version: {version.version_id}")
            row.status = version.status.value
            row.page = _page_to_dict(version.page)
            row.parent_version_id = version.parent_version_id
            session.execute(
                delete(TemplateFieldRow).where(TemplateFieldRow.version_id == version.version_id)
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

    def list_versions(self, template_key: str) -> list[TemplateVersion]:
        with self._read_session() as session:
            ids = session.scalars(
                select(TemplateVersionRow.version_id)
                .where(TemplateVersionRow.template_key == template_key)
                .order_by(TemplateVersionRow.version, TemplateVersionRow.version_id)
            ).all()
        versions = (self.get_version(version_id) for version_id in ids)
        return [version for version in versions if version is not None]

    def list_template_keys(self) -> list[str]:
        with self._read_session() as session:
            return list(
                session.scalars(
                    select(TemplateVersionRow.template_key)
                    .distinct()
                    .order_by(TemplateVersionRow.template_key)
                ).all()
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

    def remove_artifacts(self, version_id: str, download_names: set[str]) -> None:
        """Remove selected generated artifacts so an idempotent installer can repair them."""
        if not download_names:
            return
        with self._transaction() as session:
            session.execute(
                delete(TemplateArtifactRow).where(
                    TemplateArtifactRow.version_id == version_id,
                    TemplateArtifactRow.download_name.in_(download_names),
                )
            )

    def get_artifact(self, artifact_id: str) -> TemplateArtifact | None:
        with self._read_session() as session:
            row = session.get(TemplateArtifactRow, artifact_id)
            if row is None:
                return None
            return TemplateArtifact(
                artifact_id=row.artifact_id,
                version_id=row.version_id,
                kind=row.kind,
                download_name=row.download_name,
                internal_uri=row.internal_uri,
                sha256=row.sha256,
            )


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
        "recognition_engine": field.recognition_engine,
        "minimum_prefill_confidence": field.minimum_prefill_confidence,
        "rules": {
            "required": field.rules.required,
            "minimum_value": field.rules.minimum_value,
            "maximum_value": field.rules.maximum_value,
            "allowed_values": list(field.rules.allowed_values),
            "master_data_source": field.rules.master_data_source,
            "allow_exception_reason": field.rules.allow_exception_reason,
        },
        "export_target": (
            {
                "workbook": field.export_target.workbook,
                "worksheet": field.export_target.worksheet,
                "business_column": field.export_target.business_column,
            }
            if field.export_target is not None
            else None
        ),
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
    rules = value.get("rules", {})
    if not isinstance(rules, dict):
        raise ValueError("template field rules must be an object")
    raw_allowed_values = rules.get("allowed_values", [])
    if not isinstance(raw_allowed_values, list) or not all(
        isinstance(item, str) for item in raw_allowed_values
    ):
        raise ValueError("template field allowed_values must be a string array")
    raw_export_target = value.get("export_target")
    if raw_export_target is not None and not isinstance(raw_export_target, dict):
        raise ValueError("template field export_target must be an object")
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
        recognition_engine=str(value.get("recognition_engine", "manual")),
        minimum_prefill_confidence=_as_float(value.get("minimum_prefill_confidence", 1.0)),
        rules=FieldRules(
            required=bool(rules.get("required", False)),
            minimum_value=_as_optional_float(rules.get("minimum_value")),
            maximum_value=_as_optional_float(rules.get("maximum_value")),
            allowed_values=tuple(raw_allowed_values),
            master_data_source=_as_optional_string(rules.get("master_data_source")),
            allow_exception_reason=bool(rules.get("allow_exception_reason", False)),
        ),
        export_target=(
            ExportTarget(
                workbook=str(raw_export_target["workbook"]),
                worksheet=str(raw_export_target["worksheet"]),
                business_column=str(raw_export_target["business_column"]),
            )
            if isinstance(raw_export_target, dict)
            else None
        ),
    )


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    raise ValueError("template page dimension must be an integer")


def _as_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError("template confidence must be numeric")


def _as_optional_float(value: object) -> float | None:
    if value is None:
        return None
    return _as_float(value)


def _as_optional_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValueError("template field string setting must be a string")
