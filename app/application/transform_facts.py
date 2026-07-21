"""Transform electronic submissions and paper confirmations into FactRecords.

This is the critical ETL step that bridges the two source systems
(electronic mobile forms and paper OCR forms) into the unified
business-fact layer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from app.modules.electronic_forms.models_ds import ElectronicSubmissionReceipt
from app.modules.fact_records.models_ds import (
    FactExportStatus,
    FactRecord,
    FactReviewStatus,
    FactSourceType,
)


def transform_electronic_submission(
    receipt: ElectronicSubmissionReceipt,
    payload: dict[str, Any],
    *,
    employee_name: str = "",
) -> list[FactRecord]:
    """Transform one electronic submission receipt into FactRecords.

    For personal forms (single worker), returns one FactRecord with
    subject_employee_code = receipt.subject_employee_code.

    For team-leader forms, the payload contains a list of team members
    under the key 'team_members'. Each member becomes a separate
    FactRecord, so wages and statistics are correctly attributed.
    """
    team_members: list[dict[str, Any]] = payload.get("team_members", [])

    if team_members:
        return _transform_team_submission(receipt, payload, team_members)
    return [_transform_personal_submission(receipt, payload, employee_name)]


def _transform_personal_submission(
    receipt: ElectronicSubmissionReceipt,
    payload: dict[str, Any],
    employee_name: str = "",
) -> FactRecord:
    values: dict[str, Any] = payload.get("values", {})
    return _build_fact_record(
        source_type=FactSourceType.ELECTRONIC,
        source_submission_id=receipt.receipt_id,
        subject_employee_code=receipt.subject_employee_code,
        subject_employee_name=employee_name,
        values=values,
    )


def _transform_team_submission(
    receipt: ElectronicSubmissionReceipt,
    payload: dict[str, Any],
    team_members: list[dict[str, Any]],
) -> list[FactRecord]:
    records: list[FactRecord] = []
    for member in team_members:
        employee_code = member.get("employee_code", "")
        employee_name = member.get("employee_name", "")
        member_values = dict(member.get("values", {}))
        # Merge team-level context (date, shift, work order) with member values
        base_values: dict[str, Any] = payload.get("values", {})
        merged = {**base_values, **member_values}
        records.append(
            _build_fact_record(
                source_type=FactSourceType.ELECTRONIC,
                source_submission_id=receipt.receipt_id,
                subject_employee_code=employee_code,
                subject_employee_name=employee_name,
                values=merged,
            )
        )
    return records


def transform_paper_confirmation(
    form_id: str,
    confirmed_values: dict[str, Any],
    *,
    employee_code: str = "",
    employee_name: str = "",
) -> FactRecord:
    """Transform a paper OCR form confirmation into a FactRecord."""
    return _build_fact_record(
        source_type=FactSourceType.PAPER_OCR,
        source_form_id=form_id,
        subject_employee_code=employee_code or confirmed_values.get("employee_id", ""),
        subject_employee_name=employee_name or confirmed_values.get("employee_name", ""),
        values=confirmed_values,
    )


def _build_fact_record(
    *,
    source_type: FactSourceType,
    source_submission_id: str | None = None,
    source_form_id: str | None = None,
    subject_employee_code: str = "",
    subject_employee_name: str = "",
    values: dict[str, Any],
) -> FactRecord:
    """Build a FactRecord from extracted values."""
    blocks = _int_or_none(values.get("blocks_completed"))
    pieces_per = _int_or_none(values.get("pieces_per_block"))
    total = blocks * pieces_per if blocks is not None and pieces_per is not None else _int_or_none(
        values.get("total_pieces")
    )

    return FactRecord(
        fact_record_id=f"FR-{uuid4().hex}",
        source_type=source_type,
        source_submission_id=source_submission_id,
        source_form_id=source_form_id,
        subject_employee_code=subject_employee_code,
        subject_employee_name=subject_employee_name,
        workshop=_str_or_empty(values.get("workshop")),
        work_order_id=_str_or_empty(values.get("work_order_id")),
        product_id=_str_or_empty(values.get("product_id")),
        process_id=_str_or_empty(values.get("process_id")),
        production_date=_str_or_empty(values.get("production_date")),
        shift=_str_or_empty(values.get("shift")),
        blocks_completed=blocks,
        pieces_per_block=pieces_per,
        total_pieces=total,
        measurement_values=_extract_measurements(values),
        review_status=FactReviewStatus.PENDING,
        export_status=FactExportStatus.NOT_EXPORTED,
    )


def _extract_measurements(values: dict[str, Any]) -> dict[str, Any]:
    """Extract measurement-related fields from form values."""
    measurement_keys = {
        "temperature", "humidity", "weight", "density",
        "viscosity", "ph_value", "pressure", "duration_minutes",
        "glue_ratio", "dry_temperature", "dry_duration",
        "assessment_result", "qualified_quantity", "defective_quantity",
    }
    return {key: values[key] for key in measurement_keys if key in values}


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def mark_form_records_for_reexport(
    existing_records: Sequence[FactRecord],
) -> list[str]:
    """Return fact_record_ids that need reexport after a form correction."""
    return [
        record.fact_record_id
        for record in existing_records
        if record.export_status == FactExportStatus.EXPORTED
    ]
