import hashlib
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine

from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.domain.models import ExportBatch


def _mapping_hash(snapshot: tuple[dict[str, object], ...]) -> str:
    serialized = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def test_export_batch_snapshots_round_trip_with_stable_mapping_hash() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    mapping_snapshot = (
        {
            "template_id": "T1",
            "template_version": "1",
            "field_key": "employee_id",
            "target": {
                "workbook": "payroll.xlsx",
                "worksheet": "employees",
                "business_column": "employee_code",
            },
        },
    )
    batch = ExportBatch(
        export_batch_id="EXPORT-NEW",
        export_type="OUTPUT",
        filters={"review_status": "CONFIRMED", "form_ids": ["FORM-1"]},
        included_records=(("FORM-1", 3),),
        file_path="internal/exports/export-new.xlsx",
        file_sha256="a" * 64,
        exported_by="finance",
        exported_at=datetime(2026, 7, 16, 8, 30, tzinfo=UTC),
        task_id="TASK-1",
        template_snapshot={
            "templates": [{"template_id": "T1", "version": 1}],
        },
        mapping_snapshot=mapping_snapshot,
        download_name="payroll-20260716.xlsx",
    )

    repository.add_export_batch(batch)

    reloaded = repository.get_export_batch("EXPORT-NEW")
    assert reloaded == batch
    assert reloaded is not None
    assert reloaded.mapping_hash == _mapping_hash(mapping_snapshot)
    assert repository.get_export_batch_by_task("TASK-1") == batch
    with pytest.raises(FrozenInstanceError):
        reloaded.export_type = "MUTATED"  # type: ignore[misc]


def test_export_batch_mapping_hash_ignores_dictionary_key_order() -> None:
    common = {
        "export_batch_id": "EXPORT-HASH",
        "export_type": "OUTPUT",
        "filters": {},
        "included_records": (),
        "file_path": "internal/hash.xlsx",
        "file_sha256": "b" * 64,
        "exported_by": "finance",
    }
    first = ExportBatch(
        **common,
        mapping_snapshot=({"field_key": "employee_id", "worksheet": "employees"},),
    )
    second = ExportBatch(
        **common,
        mapping_snapshot=({"worksheet": "employees", "field_key": "employee_id"},),
    )

    assert first.mapping_hash == second.mapping_hash
    assert len(first.mapping_hash) == 64


def test_export_batch_history_is_newest_first_and_preserves_replacement() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    old = ExportBatch(
        "EXPORT-OLD",
        "OUTPUT",
        {},
        (("FORM-1", 1),),
        "internal/old.xlsx",
        "c" * 64,
        "finance",
        datetime(2026, 7, 15, tzinfo=UTC),
    )
    replacement = ExportBatch(
        "EXPORT-REPLACEMENT",
        "OUTPUT",
        {},
        (("FORM-1", 2),),
        "internal/replacement.xlsx",
        "d" * 64,
        "finance",
        datetime(2026, 7, 16, tzinfo=UTC),
        "EXPORT-OLD",
        task_id="TASK-REPLACEMENT",
        download_name="replacement.xlsx",
    )

    repository.add_export_batch(old)
    repository.add_export_batch(replacement)

    assert [item.export_batch_id for item in repository.list_export_batches()] == [
        "EXPORT-REPLACEMENT",
        "EXPORT-OLD",
    ]
    assert repository.get_export_batch("EXPORT-OLD") == old
    assert repository.get_export_batch("EXPORT-REPLACEMENT") == replacement
    assert replacement.supersedes_batch_id == old.export_batch_id
    assert old.task_id is None
    assert old.download_name == "export.xlsx"
