"""Business rules validation module facade."""

from collections.abc import Mapping
from typing import Any

from app.domain.models import ExportStatus
from app.domain.rules import RuleContext, RuleResult, validate


class RulesFacade:
    """Business rules validation boundary backed by pure domain logic."""

    def validate(
        self,
        values: Mapping[str, Any],
        *,
        required_fields: frozenset[str] = frozenset(),
        ranges: Mapping[str, tuple[int | float, int | float]] = {},
        valid_employee_ids: frozenset[str] = frozenset(),
        valid_work_order_ids: frozenset[str] = frozenset(),
        is_duplicate_form: bool = False,
        expected_version: int = 0,
        current_version: int = 0,
        export_status: ExportStatus = ExportStatus.NOT_EXPORTED,
        required_export_fields: frozenset[str] = frozenset(),
        export_mapping: Mapping[str, str] = {},
    ) -> list[RuleResult]:
        """Run all applicable validation rules against the given values."""
        context = RuleContext(
            values=values,
            required_fields=required_fields,
            ranges=ranges,
            valid_employee_ids=valid_employee_ids,
            valid_work_order_ids=valid_work_order_ids,
            is_duplicate_form=is_duplicate_form,
            expected_version=expected_version,
            current_version=current_version,
            export_status=export_status,
            required_export_fields=required_export_fields,
            export_mapping=export_mapping,
        )
        return validate(context)
