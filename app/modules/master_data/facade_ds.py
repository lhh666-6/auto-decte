"""Application boundary for versioned master-data management."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import uuid4

from app.modules.master_data.models_ds import (
    MasterDataAudit,
    MasterDataCatalog,
    MasterDataNotFound,
    MasterDataRecord,
)
from app.modules.master_data.repository_ds import SqlAlchemyMasterDataRepository


class MasterDataFacade:
    def __init__(
        self,
        repository: SqlAlchemyMasterDataRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def create(
        self,
        catalog: MasterDataCatalog,
        code: str,
        display_name: str,
        attributes: Mapping[str, object],
        actor_id: str,
        reason: str,
    ) -> MasterDataRecord:
        now = self._clock()
        record = MasterDataRecord(
            catalog=catalog,
            code=_required(code, "code"),
            display_name=_required(display_name, "display_name"),
            attributes=dict(attributes),
            active=True,
            revision=1,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self._repository.create(
            record,
            self._audit(record, "CREATE", actor_id, reason, before=None),
        )
        return record

    def get(self, catalog: MasterDataCatalog, code: str) -> MasterDataRecord:
        record = self._repository.get(catalog, code)
        if record is None:
            raise MasterDataNotFound(code)
        return record

    def list_records(
        self,
        catalog: MasterDataCatalog,
        *,
        include_inactive: bool = False,
        query: str | None = None,
    ) -> list[MasterDataRecord]:
        return self._repository.list_records(
            catalog,
            include_inactive=include_inactive,
            query=query.strip() if query and query.strip() else None,
        )

    def update(
        self,
        catalog: MasterDataCatalog,
        code: str,
        expected_revision: int,
        actor_id: str,
        reason: str,
        *,
        display_name: str | None = None,
        attributes: Mapping[str, object] | None = None,
    ) -> MasterDataRecord:
        current = self.get(catalog, code)
        updated = replace(
            current,
            display_name=(
                _required(display_name, "display_name")
                if display_name is not None
                else current.display_name
            ),
            attributes=dict(attributes) if attributes is not None else current.attributes,
            revision=current.revision + 1,
            updated_at=self._clock(),
            updated_by=actor_id,
        )
        self._repository.update(
            updated,
            self._audit(updated, "UPDATE", actor_id, reason, before=current),
            expected_revision,
        )
        return updated

    def set_active(
        self,
        catalog: MasterDataCatalog,
        code: str,
        active: bool,
        expected_revision: int,
        actor_id: str,
        reason: str,
    ) -> MasterDataRecord:
        current = self.get(catalog, code)
        updated = replace(
            current,
            active=active,
            revision=current.revision + 1,
            updated_at=self._clock(),
            updated_by=actor_id,
        )
        self._repository.update(
            updated,
            self._audit(
                updated,
                "REACTIVATE" if active else "DEACTIVATE",
                actor_id,
                reason,
                before=current,
            ),
            expected_revision,
        )
        return updated

    def audits(self, catalog: MasterDataCatalog, code: str) -> list[MasterDataAudit]:
        self.get(catalog, code)
        return self._repository.list_audits(catalog, code)

    def is_active(self, source: str, code: str) -> bool:
        try:
            catalog = MasterDataCatalog(source)
        except ValueError:
            return False
        return self._repository.is_active(catalog, code)

    def options(self, source: str) -> list[dict[str, str]]:
        try:
            catalog = MasterDataCatalog(source)
        except ValueError:
            return []
        return [
            {"value": record.code, "label": record.display_name}
            for record in self.list_records(catalog)
        ]

    def _audit(
        self,
        record: MasterDataRecord,
        event_type: str,
        actor_id: str,
        reason: str,
        *,
        before: MasterDataRecord | None,
    ) -> MasterDataAudit:
        return MasterDataAudit(
            audit_id=f"MD-AUDIT-{uuid4().hex}",
            catalog=record.catalog,
            code=record.code,
            revision=record.revision,
            event_type=event_type,
            actor_id=actor_id,
            timestamp=record.updated_at,
            before=_snapshot(before),
            after=_snapshot(record),
            reason=_required(reason, "reason"),
        )


def _required(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} is required")
    return cleaned


def _snapshot(record: MasterDataRecord | None) -> dict[str, object] | None:
    if record is None:
        return None
    snapshot = asdict(record)
    snapshot["catalog"] = record.catalog.value
    snapshot["created_at"] = record.created_at.isoformat()
    snapshot["updated_at"] = record.updated_at.isoformat()
    return snapshot
