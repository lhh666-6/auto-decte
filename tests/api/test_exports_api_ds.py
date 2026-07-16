from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.application.import_forms import ImportForms
from app.application.review_forms import ReviewForms
from app.domain.models import ExportBatch
from app.domain.templates_ds import (
    ExportTarget,
    FieldDefinition,
    FieldRules,
    PageSpec,
    Rect,
    TemplateVersion,
)
from app.modules.tasks.models_ds import TaskCommand
from app.services.container import Services, build_services
from config.settings import Settings

FINANCE = {"X-Actor-ID": "finance-a", "X-Roles": "FINANCE"}
OPERATOR = {"X-Actor-ID": "operator-a", "X-Roles": "OPERATOR"}


def _build_client(tmp_path: Path) -> tuple[TestClient, Services]:
    services = build_services(Settings(data_root=tmp_path / "runtime", allow_header_identity=True))
    page = PageSpec.a4_portrait()
    template = TemplateVersion.draft("TPL-T1-V1", "T1", 1, page)
    template.add_field(
        FieldDefinition(
            "employee_id",
            "Employee",
            "text",
            "text_box",
            Rect(0.1, 0.1, 0.2, 0.05),
            page,
            rules=FieldRules(required=True, allowed_values=("E001",)),
            export_target=ExportTarget("payroll.xlsx", "employees", "employee_code"),
        )
    )
    template.add_field(
        FieldDefinition(
            "quantity",
            "Quantity",
            "integer",
            "number_box",
            Rect(0.1, 0.2, 0.2, 0.05),
            page,
            rules=FieldRules(required=True, minimum_value=1, maximum_value=10),
            export_target=ExportTarget("payroll.xlsx", "employees", "quantity"),
        )
    )
    services.template_repository.add_version(template)
    imports = ImportForms(
        services.repository,
        services.repository,
        services.repository,
        services.evidence_storage,
    )
    reviews = ReviewForms(services.repository, services.repository)
    for form_id, values in (
        ("FORM-VALID", {"employee_id": "E001", "quantity": 5}),
        ("FORM-INVALID", {"employee_id": "BAD", "quantity": 99}),
        ("FORM-MISSING", {}),
    ):
        image = tmp_path / f"{form_id}.png"
        image.write_bytes(form_id.encode())
        evidence = imports.import_image(image, form_id, "T1", "1", "operator-a")
        reviews.confirm(
            form_id,
            0,
            values,
            "reviewer-a",
            "confirmed",
            (evidence.file_id,),
        )
    return TestClient(create_app(services), raise_server_exceptions=False), services


def test_preview_is_read_only_and_returns_field_level_exclusion_reasons(
    tmp_path: Path,
) -> None:
    client, services = _build_client(tmp_path)
    form_ids = ("FORM-VALID", "FORM-INVALID", "FORM-MISSING")
    before = [services.repository.get_form(form_id) for form_id in form_ids]

    response = client.get("/api/v1/exports/preview", headers=FINANCE)

    assert response.status_code == 200
    body = response.json()
    assert body["included"] == [{"form_id": "FORM-VALID", "record_version": 1}]
    assert body["excluded"][0]["form_id"] == "FORM-INVALID"
    assert body["excluded"][0]["reason"] == "FINAL_VALIDATION_FAILED"
    assert {
        (reason["scope"], reason["code"], reason.get("field_key"))
        for reason in body["excluded"][0]["reasons"]
    } == {
        ("FIELD", "VALUE_NOT_ALLOWED", "employee_id"),
        ("FIELD", "VALUE_ABOVE_MAXIMUM", "quantity"),
    }
    missing = next(item for item in body["excluded"] if item["form_id"] == "FORM-MISSING")
    assert {(reason["code"], reason["field_key"]) for reason in missing["reasons"]} == {
        ("REQUIRED_VALUE_MISSING", "employee_id"),
        ("REQUIRED_VALUE_MISSING", "quantity"),
    }
    assert body["mapping_snapshot"][0]["field_key"] == "employee_id"
    assert [services.repository.get_form(form_id) for form_id in form_ids] == before
    assert services.repository.list_export_batches() == []


def test_preview_requires_export_permission(tmp_path: Path) -> None:
    client, _ = _build_client(tmp_path)

    response = client.get("/api/v1/exports/preview", headers=OPERATOR)

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_finance_creates_fixed_scope_export_task_and_terminal_replay_is_not_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, services = _build_client(tmp_path)
    calls = 0
    original_handle = services.export_handler.handle

    def counted_handle(task_id: str) -> object:
        nonlocal calls
        calls += 1
        return original_handle(task_id)

    monkeypatch.setattr(services.export_handler, "handle", counted_handle)
    headers = {**FINANCE, "Idempotency-Key": "export-valid"}
    body = {
        "export_type": "PAYROLL",
        "filters": {"form_id": "FORM-VALID"},
    }

    first = client.post("/api/v1/exports", headers=headers, json=body)
    second = client.post("/api/v1/exports", headers=headers, json=body)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["task_id"] == second.json()["task_id"]
    assert first.json()["status_url"] == f"/api/v1/tasks/{first.json()['task_id']}"
    assert first.json()["events_url"].endswith("/events")
    task = services.tasks.get(first.json()["task_id"])
    assert task.operation == "XLSX_EXPORT"
    assert task.resource_id == "EXPORTS"
    assert task.actor_id == "finance-a"
    assert calls == 1


def test_export_creation_requires_permission_and_idempotency_key(tmp_path: Path) -> None:
    client, _ = _build_client(tmp_path)
    body = {"export_type": "PAYROLL", "filters": {}}

    operator = client.post(
        "/api/v1/exports",
        headers={**OPERATOR, "Idempotency-Key": "operator-export"},
        json=body,
    )
    missing_key = client.post("/api/v1/exports", headers=FINANCE, json=body)

    assert operator.status_code == 403
    assert operator.json()["code"] == "PERMISSION_DENIED"
    assert missing_key.status_code == 400
    assert missing_key.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_same_export_key_with_different_payload_returns_conflict(tmp_path: Path) -> None:
    client, _ = _build_client(tmp_path)
    headers = {**FINANCE, "Idempotency-Key": "conflicting-export"}

    first = client.post(
        "/api/v1/exports",
        headers=headers,
        json={"export_type": "PAYROLL", "filters": {"form_id": "FORM-VALID"}},
    )
    conflict = client.post(
        "/api/v1/exports",
        headers=headers,
        json={"export_type": "PAYROLL", "filters": {"form_id": "FORM-INVALID"}},
    )

    assert first.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_export_creator_can_read_own_task_status_and_safe_events(tmp_path: Path) -> None:
    client, _ = _build_client(tmp_path)
    created = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "read-own-export"},
        json={"export_type": "PAYROLL", "filters": {"form_id": "FORM-VALID"}},
    ).json()

    task_response = client.get(created["status_url"], headers=FINANCE)
    events_response = client.get(created["events_url"], headers=FINANCE)

    assert task_response.status_code == 200
    assert task_response.json()["operation"] == "XLSX_EXPORT"
    assert events_response.status_code == 200
    assert "event: SUCCEEDED" in events_response.text
    assert "export_batch_id" not in events_response.text


def test_finance_cannot_read_another_actors_export_or_non_export_task(
    tmp_path: Path,
) -> None:
    client, services = _build_client(tmp_path)
    created = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "private-export"},
        json={"export_type": "PAYROLL", "filters": {"form_id": "FORM-VALID"}},
    ).json()
    non_export = services.tasks.submit(
        TaskCommand("FORM_RECOGNITION", "FORM-VALID", "finance-a", "not-export", {})
    )
    other_finance = {"X-Actor-ID": "finance-b", "X-Roles": "FINANCE"}

    other_status = client.get(created["status_url"], headers=other_finance)
    other_events = client.get(created["events_url"], headers=other_finance)
    non_export_status = client.get(f"/api/v1/tasks/{non_export.task_id}", headers=FINANCE)
    unknown = client.get("/api/v1/tasks/TASK-MISSING", headers=FINANCE)

    assert other_status.status_code == 403
    assert other_events.status_code == 403
    assert non_export_status.status_code == 403
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "TASK_NOT_FOUND"


def test_batch_list_and_detail_are_newest_first_json_safe_and_hide_paths(
    tmp_path: Path,
) -> None:
    client, services = _build_client(tmp_path)
    first = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "batch-one"},
        json={"export_type": "PAYROLL", "filters": {"form_id": "FORM-VALID"}},
    ).json()
    second = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "batch-two"},
        json={"export_type": "PAYROLL", "filters": {"form_id": "FORM-VALID"}},
    ).json()
    expected = [
        services.repository.get_export_batch_by_task(task_id)
        for task_id in (second["task_id"], first["task_id"])
    ]
    assert all(batch is not None for batch in expected)

    listed = client.get("/api/v1/exports/batches", headers=FINANCE)
    detail = client.get(
        f"/api/v1/exports/batches/{expected[0].export_batch_id}",  # type: ignore[union-attr]
        headers=FINANCE,
    )

    assert listed.status_code == 200
    assert [item["export_batch_id"] for item in listed.json()] == [
        batch.export_batch_id for batch in expected if batch is not None
    ]
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["template_snapshot"]["templates"][0]["template_key"] == "T1"
    assert payload["mapping_snapshot"][0]["field_key"] == "employee_id"
    assert payload["included_records"] == [{"form_id": "FORM-VALID", "record_version": 1}]
    assert payload["download_url"].endswith("/download")
    assert "file_path" not in payload
    assert str(services.settings.exports_root) not in listed.text
    assert str(services.settings.exports_root) not in detail.text


def test_batch_download_checks_permission_content_filename_and_integrity(
    tmp_path: Path,
) -> None:
    client, services = _build_client(tmp_path)
    task = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "download-export"},
        json={"export_type": "PAYROLL", "filters": {"form_id": "FORM-VALID"}},
    ).json()
    batch = services.repository.get_export_batch_by_task(task["task_id"])
    assert batch is not None

    downloaded = client.get(
        f"/api/v1/exports/batches/{batch.export_batch_id}/download", headers=FINANCE
    )
    denied = client.get(
        f"/api/v1/exports/batches/{batch.export_batch_id}/download", headers=OPERATOR
    )

    assert downloaded.status_code == 200
    assert downloaded.content == Path(batch.file_path).read_bytes()
    assert batch.download_name in downloaded.headers["content-disposition"]
    assert denied.status_code == 403


def test_batch_download_rejects_escape_missing_and_hash_mismatch_without_path_leak(
    tmp_path: Path,
) -> None:
    client, services = _build_client(tmp_path)
    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(b"outside")
    missing = services.settings.exports_root / "missing.xlsx"
    corrupt = services.settings.exports_root / "corrupt.xlsx"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_bytes(b"corrupt")
    for batch_id, path, digest in (
        ("EXPORT-ESCAPE", outside, sha256(outside.read_bytes()).hexdigest()),
        ("EXPORT-MISSING", missing, "0" * 64),
        ("EXPORT-CORRUPT", corrupt, "0" * 64),
    ):
        services.repository.add_export_batch(
            ExportBatch(
                export_batch_id=batch_id,
                export_type="PAYROLL",
                filters={},
                included_records=(),
                file_path=str(path),
                file_sha256=digest,
                exported_by="finance-a",
                download_name=f"{batch_id}.xlsx",
            )
        )

    escaped = client.get("/api/v1/exports/batches/EXPORT-ESCAPE/download", headers=FINANCE)
    gone = client.get("/api/v1/exports/batches/EXPORT-MISSING/download", headers=FINANCE)
    mismatch = client.get("/api/v1/exports/batches/EXPORT-CORRUPT/download", headers=FINANCE)
    unknown = client.get("/api/v1/exports/batches/EXPORT-UNKNOWN/download", headers=FINANCE)

    assert escaped.status_code == 409
    assert escaped.json()["code"] == "EXPORT_PATH_INVALID"
    assert gone.status_code == 410
    assert gone.json()["code"] == "EXPORT_FILE_GONE"
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "EXPORT_HASH_MISMATCH"
    assert unknown.status_code == 404
    assert str(outside) not in escaped.text
    assert str(missing) not in gone.text
    assert str(corrupt) not in mismatch.text


def test_reexport_without_superseded_batch_is_accepted_then_persistently_failed(
    tmp_path: Path,
) -> None:
    client, services = _build_client(tmp_path)
    first = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "reexport-base"},
        json={"export_type": "PAYROLL", "filters": {"form_id": "FORM-VALID"}},
    )
    assert first.status_code == 202
    ReviewForms(services.repository, services.repository).confirm(
        "FORM-VALID",
        1,
        {"employee_id": "E001", "quantity": 6},
        "reviewer-a",
        "correction",
        (),
    )

    response = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "reexport-without-base"},
        json={
            "export_type": "PAYROLL",
            "filters": {"export_status": "REEXPORT_REQUIRED"},
        },
    )

    assert response.status_code == 202
    task = services.tasks.get(response.json()["task_id"])
    assert task.status.value == "FAILED"
    assert task.error is not None
    assert "supersedes_batch_id is required" in task.error
    assert len(services.repository.list_export_batches()) == 1
