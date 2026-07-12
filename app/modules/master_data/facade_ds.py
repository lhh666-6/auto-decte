"""Master data management module facade."""

from collections.abc import Mapping


class MasterDataFacade:
    """Master data boundary backed by in-memory reference data.

    In a production deployment these lookups would be backed by a database
    or an external master-data service.  The current in-memory approach is
    suitable for the Demo deployment.
    """

    def __init__(
        self,
        valid_employee_ids: frozenset[str] = frozenset(),
        valid_work_order_ids: frozenset[str] = frozenset(),
        field_ranges: Mapping[str, tuple[int | float, int | float]] = {},
        field_labels: Mapping[str, str] = {},
    ) -> None:
        self._valid_employee_ids = valid_employee_ids
        self._valid_work_order_ids = valid_work_order_ids
        self._field_ranges = dict(field_ranges)
        self._field_labels = dict(field_labels)

    # --- Employee data ---

    @property
    def valid_employee_ids(self) -> frozenset[str]:
        """Return the known set of valid employee identifiers."""
        return self._valid_employee_ids

    def is_valid_employee(self, employee_id: str) -> bool:
        """Check whether an employee id is known in master data."""
        return employee_id in self._valid_employee_ids

    # --- Work order data ---

    @property
    def valid_work_order_ids(self) -> frozenset[str]:
        """Return the known set of valid work order identifiers."""
        return self._valid_work_order_ids

    def is_valid_work_order(self, work_order_id: str) -> bool:
        """Check whether a work order id is known in master data."""
        return work_order_id in self._valid_work_order_ids

    # --- Field metadata ---

    def field_range(self, field_id: str) -> tuple[int | float, int | float] | None:
        """Return the allowed (min, max) for a numeric field, or ``None``."""
        return self._field_ranges.get(field_id)

    def field_label(self, field_id: str) -> str | None:
        """Return the human-readable label for a field, or ``None``."""
        return self._field_labels.get(field_id)
