"""Master-data records and audit value objects."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MasterDataCatalog(StrEnum):
    EMPLOYEES = "employees"
    WORK_ORDERS = "work-orders"
    PRODUCTS = "products"
    PROCESSES = "processes"


@dataclass(frozen=True, slots=True)
class MasterDataRecord:
    catalog: MasterDataCatalog
    code: str
    display_name: str
    attributes: dict[str, object]
    active: bool
    revision: int
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


@dataclass(frozen=True, slots=True)
class MasterDataAudit:
    audit_id: str
    catalog: MasterDataCatalog
    code: str
    revision: int
    event_type: str
    actor_id: str
    timestamp: datetime
    before: dict[str, object] | None
    after: dict[str, object] | None
    reason: str


class MasterDataAlreadyExists(Exception):
    pass


class MasterDataNotFound(Exception):
    pass


class MasterDataRevisionConflict(Exception):
    def __init__(self, submitted_revision: int, current_revision: int) -> None:
        super().__init__(
            f"Submitted revision {submitted_revision} does not match {current_revision}"
        )
        self.submitted_revision = submitted_revision
        self.current_revision = current_revision
