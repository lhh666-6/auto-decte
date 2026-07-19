"""SQLAlchemy persistence adapter for immutable template versions."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    JobProfileVersionRow,
    TemplateArtifactRow,
    TemplateFieldRow,
    TemplateMetadataRow,
    TemplateVersionRow,
)
from app.domain.templates_ds import (
    CoreLayoutKind,
    ElementKind,
    ExportTarget,
    FieldDefinition,
    FieldRules,
    FillPolicy,
    JobProfileStatus,
    PageSpec,
    PaperEntryMode,
    PayrollJobProfileVersion,
    PrintImposition,
    RecognitionMode,
    Rect,
    StaticElement,
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
            if session.get(TemplateMetadataRow, version.template_key) is None:
                session.add(
                    TemplateMetadataRow(
                        template_key=version.template_key,
                        display_name=version.template_key,
                        description="",
                    )
                )
            session.add(
                TemplateVersionRow(
                    version_id=version.version_id,
                    template_key=version.template_key,
                    version=version.version,
                    status=version.status.value,
                    page=_page_to_dict(version.page),
                    parent_version_id=version.parent_version_id,
                    static_elements=[
                        _static_element_to_dict(element) for element in version.static_elements
                    ],
                    print_imposition=_print_imposition_to_dict(version.print_imposition),
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

    def add_job_profile(self, profile: PayrollJobProfileVersion) -> None:
        with self._transaction() as session:
            if session.get(TemplateVersionRow, profile.template_version_id) is None:
                raise KeyError(f"Unknown template version: {profile.template_version_id}")
            session.add(_job_profile_to_row(profile))

    def get_job_profile(
        self, profile_version_id: str
    ) -> PayrollJobProfileVersion | None:
        with self._read_session() as session:
            row = session.get(JobProfileVersionRow, profile_version_id)
            return _job_profile_from_row(row) if row is not None else None

    def get_job_profile_by_key_version(
        self, profile_key: str, version: int
    ) -> PayrollJobProfileVersion | None:
        with self._read_session() as session:
            row = session.scalar(
                select(JobProfileVersionRow).where(
                    JobProfileVersionRow.profile_key == profile_key,
                    JobProfileVersionRow.version == version,
                )
            )
            return _job_profile_from_row(row) if row is not None else None

    def list_job_profiles(self, profile_key: str) -> list[PayrollJobProfileVersion]:
        with self._read_session() as session:
            rows = session.scalars(
                select(JobProfileVersionRow)
                .where(JobProfileVersionRow.profile_key == profile_key)
                .order_by(JobProfileVersionRow.version, JobProfileVersionRow.profile_version_id)
            ).all()
            return [_job_profile_from_row(row) for row in rows]

    def replace_job_profile(self, profile: PayrollJobProfileVersion) -> None:
        with self._transaction() as session:
            row = session.get(JobProfileVersionRow, profile.profile_version_id)
            if row is None:
                raise KeyError(f"Unknown job profile version: {profile.profile_version_id}")
            persisted = _job_profile_from_row(row)
            _validate_job_profile_transition(persisted, profile)
            row.status = profile.status.value
            if persisted.status in {JobProfileStatus.PUBLISHED, JobProfileStatus.RETIRED}:
                return
            row.display_name = profile.display_name
            row.core_layout = profile.core_layout.value
            row.template_version_id = profile.template_version_id
            row.template_version = profile.template_version
            row.parent_profile_version_id = profile.parent_profile_version_id
            row.unit = profile.unit
            row.fixed_options = profile.fixed_options
            row.pricing_rules = profile.pricing_rules
            row.deduction_rules = profile.deduction_rules
            row.export_mapping = profile.export_mapping

    def get_version(self, version_id: str) -> TemplateVersion | None:
        with self._read_session() as session:
            row = session.get(TemplateVersionRow, version_id)
            if row is None:
                return None
            return _version_from_row(session, row)

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
            persisted = _version_from_row(session, row)
            _validate_repository_transition(persisted, version)
            if persisted.status in {
                TemplateStatus.PUBLISHED,
                TemplateStatus.DEPRECATED,
                TemplateStatus.RETIRED,
            }:
                row.status = version.status.value
                return
            row.status = version.status.value
            row.page = _page_to_dict(version.page)
            row.parent_version_id = version.parent_version_id
            row.static_elements = [
                _static_element_to_dict(element) for element in version.static_elements
            ]
            row.print_imposition = _print_imposition_to_dict(version.print_imposition)
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

    def get_template_metadata(self, template_key: str) -> tuple[str, str] | None:
        with self._read_session() as session:
            row = session.get(TemplateMetadataRow, template_key)
            if row is None:
                return None
            return row.display_name, row.description

    def update_template_metadata(
        self, template_key: str, display_name: str, description: str
    ) -> None:
        with self._transaction() as session:
            row = session.get(TemplateMetadataRow, template_key)
            if row is None:
                raise KeyError(f"Unknown template: {template_key}")
            row.display_name = display_name
            row.description = description

    def delete_version(self, version_id: str) -> None:
        with self._transaction() as session:
            row = session.get(TemplateVersionRow, version_id)
            if row is None:
                raise KeyError(f"Unknown template version: {version_id}")
            if TemplateStatus(row.status) in {
                TemplateStatus.PUBLISHED,
                TemplateStatus.DEPRECATED,
                TemplateStatus.RETIRED,
            }:
                raise ValueError("published template versions cannot be deleted")
            template_key = row.template_key
            session.execute(
                delete(TemplateArtifactRow).where(TemplateArtifactRow.version_id == version_id)
            )
            session.execute(
                delete(TemplateFieldRow).where(TemplateFieldRow.version_id == version_id)
            )
            session.delete(row)
            session.flush()
            remaining = session.scalar(
                select(TemplateVersionRow.version_id)
                .where(TemplateVersionRow.template_key == template_key)
                .limit(1)
            )
            if remaining is None:
                metadata = session.get(TemplateMetadataRow, template_key)
                if metadata is not None:
                    session.delete(metadata)

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


def _job_profile_to_row(profile: PayrollJobProfileVersion) -> JobProfileVersionRow:
    return JobProfileVersionRow(
        profile_version_id=profile.profile_version_id,
        profile_key=profile.profile_key,
        version=profile.version,
        display_name=profile.display_name,
        core_layout=profile.core_layout.value,
        template_version_id=profile.template_version_id,
        template_version=profile.template_version,
        status=profile.status.value,
        parent_profile_version_id=profile.parent_profile_version_id,
        unit=profile.unit,
        fixed_options=profile.fixed_options,
        pricing_rules=profile.pricing_rules,
        deduction_rules=profile.deduction_rules,
        export_mapping=profile.export_mapping,
    )


def _job_profile_from_row(row: JobProfileVersionRow) -> PayrollJobProfileVersion:
    return PayrollJobProfileVersion(
        profile_version_id=row.profile_version_id,
        profile_key=row.profile_key,
        version=row.version,
        display_name=row.display_name,
        core_layout=CoreLayoutKind(row.core_layout),
        template_version_id=row.template_version_id,
        template_version=row.template_version,
        status=JobProfileStatus(row.status),
        parent_profile_version_id=row.parent_profile_version_id,
        unit=row.unit,
        fixed_options=dict(row.fixed_options),
        pricing_rules=dict(row.pricing_rules),
        deduction_rules=dict(row.deduction_rules),
        export_mapping=dict(row.export_mapping),
    )


def _validate_job_profile_transition(
    persisted: PayrollJobProfileVersion, replacement: PayrollJobProfileVersion
) -> None:
    allowed_statuses = {
        JobProfileStatus.DRAFT: {
            JobProfileStatus.DRAFT,
            JobProfileStatus.READY_TO_PUBLISH,
        },
        JobProfileStatus.READY_TO_PUBLISH: {
            JobProfileStatus.DRAFT,
            JobProfileStatus.READY_TO_PUBLISH,
            JobProfileStatus.PUBLISHED,
        },
        JobProfileStatus.PUBLISHED: {
            JobProfileStatus.PUBLISHED,
            JobProfileStatus.RETIRED,
        },
        JobProfileStatus.RETIRED: {JobProfileStatus.RETIRED},
    }
    if replacement.status not in allowed_statuses[persisted.status]:
        raise ValueError("invalid job profile lifecycle transition")
    if persisted.status not in {JobProfileStatus.PUBLISHED, JobProfileStatus.RETIRED}:
        return
    persisted_content = (
        persisted.profile_version_id,
        persisted.profile_key,
        persisted.version,
        persisted.display_name,
        persisted.core_layout,
        persisted.template_version_id,
        persisted.template_version,
        persisted.parent_profile_version_id,
        persisted.unit,
        persisted.fixed_options,
        persisted.pricing_rules,
        persisted.deduction_rules,
        persisted.export_mapping,
    )
    replacement_content = (
        replacement.profile_version_id,
        replacement.profile_key,
        replacement.version,
        replacement.display_name,
        replacement.core_layout,
        replacement.template_version_id,
        replacement.template_version,
        replacement.parent_profile_version_id,
        replacement.unit,
        replacement.fixed_options,
        replacement.pricing_rules,
        replacement.deduction_rules,
        replacement.export_mapping,
    )
    if persisted_content != replacement_content:
        raise ValueError("published job profile versions cannot be replaced")


def _version_from_row(session: Session, row: TemplateVersionRow) -> TemplateVersion:
    field_rows = session.scalars(
        select(TemplateFieldRow)
        .where(TemplateFieldRow.version_id == row.version_id)
        .order_by(TemplateFieldRow.position, TemplateFieldRow.field_id)
    ).all()
    page = _page_from_dict(row.page)
    return TemplateVersion(
        version_id=row.version_id,
        template_key=row.template_key,
        version=row.version,
        page=page,
        status=TemplateStatus(row.status),
        fields=[
            _field_from_dict(item.field_key, item.definition, page) for item in field_rows
        ],
        parent_version_id=row.parent_version_id,
        static_elements=_static_elements_from_value(row.static_elements),
        print_imposition=_print_imposition_from_value(row.print_imposition),
    )


def _validate_repository_transition(
    persisted: TemplateVersion, replacement: TemplateVersion
) -> None:
    if persisted.version_id != replacement.version_id:
        raise ValueError("template version identity cannot change")
    allowed_statuses = {
        TemplateStatus.DRAFT: {
            TemplateStatus.DRAFT,
            TemplateStatus.PREFLIGHT_FAILED,
            TemplateStatus.READY_TO_PUBLISH,
        },
        TemplateStatus.PREFLIGHT_FAILED: {
            TemplateStatus.DRAFT,
            TemplateStatus.PREFLIGHT_FAILED,
            TemplateStatus.READY_TO_PUBLISH,
        },
        TemplateStatus.READY_TO_PUBLISH: {
            TemplateStatus.DRAFT,
            TemplateStatus.PREFLIGHT_FAILED,
            TemplateStatus.READY_TO_PUBLISH,
            TemplateStatus.PUBLISHED,
        },
        TemplateStatus.PUBLISHED: {
            TemplateStatus.PUBLISHED,
            TemplateStatus.DEPRECATED,
            TemplateStatus.RETIRED,
        },
        TemplateStatus.DEPRECATED: {
            TemplateStatus.DEPRECATED,
            TemplateStatus.RETIRED,
        },
        TemplateStatus.RETIRED: {TemplateStatus.RETIRED},
    }
    if replacement.status not in allowed_statuses[persisted.status]:
        raise ValueError("invalid template lifecycle transition")
    if persisted.status not in {
        TemplateStatus.PUBLISHED,
        TemplateStatus.DEPRECATED,
        TemplateStatus.RETIRED,
    }:
        return
    if (
        persisted.template_key != replacement.template_key
        or persisted.version != replacement.version
        or persisted.page != replacement.page
        or persisted.fields != replacement.fields
        or persisted.parent_version_id != replacement.parent_version_id
        or persisted.static_elements != replacement.static_elements
        or persisted.print_imposition != replacement.print_imposition
    ):
        raise ValueError("published template versions cannot be replaced")


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
        width_mm=_as_number(value["width_mm"]),
        height_mm=_as_number(value["height_mm"]),
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
        "paper_entry_mode": field.paper_entry_mode.value if field.paper_entry_mode else None,
        "recognition_mode": field.recognition_mode.value if field.recognition_mode else None,
        "fill_policy": field.fill_policy.value if field.fill_policy else None,
        "confidence_threshold": field.confidence_threshold,
        "requires_manual_confirmation": field.requires_manual_confirmation,
        "calculation_expression": field.calculation_expression,
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
        paper_entry_mode=(
            PaperEntryMode(str(value["paper_entry_mode"]))
            if value.get("paper_entry_mode") is not None
            else None
        ),
        recognition_mode=(
            RecognitionMode(str(value["recognition_mode"]))
            if value.get("recognition_mode") is not None
            else None
        ),
        fill_policy=(
            FillPolicy(str(value["fill_policy"]))
            if value.get("fill_policy") is not None
            else None
        ),
        confidence_threshold=_as_optional_float(value.get("confidence_threshold")),
        requires_manual_confirmation=bool(value.get("requires_manual_confirmation", False)),
        calculation_expression=_as_optional_string(value.get("calculation_expression")),
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


def _static_element_to_dict(element: StaticElement) -> dict[str, object]:
    return {
        "element_id": element.element_id,
        "kind": element.kind.value,
        "text": element.text,
        "region": {
            "x": element.region.x,
            "y": element.region.y,
            "width": element.region.width,
            "height": element.region.height,
        },
    }


def _static_elements_from_value(value: object) -> list[StaticElement]:
    if not isinstance(value, list):
        raise ValueError("template static_elements must be an array")
    elements: list[StaticElement] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("template static element must be an object")
        region = item.get("region")
        if not isinstance(region, dict):
            raise ValueError("template static element region must be an object")
        elements.append(
            StaticElement(
                element_id=str(item["element_id"]),
                kind=ElementKind(str(item["kind"])),
                region=Rect(
                    x=_as_float(region["x"]),
                    y=_as_float(region["y"]),
                    width=_as_float(region["width"]),
                    height=_as_float(region["height"]),
                ),
                text=str(item.get("text", "")),
            )
        )
    return elements


def _print_imposition_to_dict(imposition: PrintImposition | None) -> dict[str, object] | None:
    if imposition is None:
        return None
    return {
        "carrier": _page_to_dict(imposition.carrier),
        "columns": imposition.columns,
        "rows": imposition.rows,
        "horizontal_gap_mm": imposition.horizontal_gap_mm,
        "vertical_gap_mm": imposition.vertical_gap_mm,
        "margin_mm": imposition.margin_mm,
        "include_cut_lines": imposition.include_cut_lines,
    }


def _print_imposition_from_value(value: object) -> PrintImposition | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("template print_imposition must be an object")
    carrier = value.get("carrier")
    if not isinstance(carrier, dict):
        raise ValueError("template print_imposition carrier must be an object")
    return PrintImposition(
        carrier=_page_from_dict(carrier),
        columns=_as_int(value.get("columns", 1)),
        rows=_as_int(value.get("rows", 1)),
        horizontal_gap_mm=_as_float(value.get("horizontal_gap_mm", 0)),
        vertical_gap_mm=_as_float(value.get("vertical_gap_mm", 0)),
        margin_mm=_as_float(value.get("margin_mm", 0)),
        include_cut_lines=bool(value.get("include_cut_lines", True)),
    )


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    raise ValueError("template page dimension must be an integer")


def _as_number(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError("template page dimension must be numeric")


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
