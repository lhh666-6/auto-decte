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
ADMIN = {"X-Actor-ID": "admin-a", "X-Roles": "ADMIN"}
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
    draft_image = tmp_path / "FORM-DRAFT.png"
    draft_image.write_bytes(b"draft")
    imports.import_image(draft_image, "FORM-DRAFT", "T1", "1", "operator-a")
    return TestClient(create_app(services), raise_server_exceptions=False), services


def test_preview_is_read_only_and_returns_field_level_exclusion_reasons(
    tmp_path: Path,
) -> None:
    client, services = _build_client(tmp_path)
    form_ids = ("FORM-VALID", "FORM-INVALID", "FORM-MISSING", "FORM-DRAFT")
    before = [services.repository.get_form(form_id) for form_id in form_ids]

    response = client.get("/api/v1/exports/preview", headers=FINANCE)

    assert response.status_code == 200
    body = response.json()
    assert body["included"] == [{"form_id": "FORM-VALID", "record_version": 1}]
    invalid = next(item for item in body["excluded"] if item["form_id"] == "FORM-INVALID")
    assert invalid["reason"] == "FINAL_VALIDATION_FAILED"
    assert {
        (reason["scope"], reason["code"], reason.get("field_key"))
        for reason in invalid["reasons"]
    } == {
        ("FIELD", "VALUE_NOT_ALLOWED", "employee_id"),
        ("FIELD", "VALUE_ABOVE_MAXIMUM", "quantity"),
    }
    invalid_reasons = {
        reason["code"]: reason for reason in invalid["reasons"]
    }
    assert invalid_reasons["VALUE_NOT_ALLOWED"]["allowed_values"] == ["E001"]
    assert "required" not in invalid_reasons["VALUE_NOT_ALLOWED"]
    assert "minimum_value" not in invalid_reasons["VALUE_NOT_ALLOWED"]
    assert "maximum_value" not in invalid_reasons["VALUE_NOT_ALLOWED"]
    assert invalid_reasons["VALUE_ABOVE_MAXIMUM"]["minimum_value"] == 1
    assert invalid_reasons["VALUE_ABOVE_MAXIMUM"]["maximum_value"] == 10
    assert "required" not in invalid_reasons["VALUE_ABOVE_MAXIMUM"]
    assert "allowed_values" not in invalid_reasons["VALUE_ABOVE_MAXIMUM"]
    missing = next(item for item in body["excluded"] if item["form_id"] == "FORM-MISSING")
    assert {(reason["code"], reason["field_key"]) for reason in missing["reasons"]} == {
        ("REQUIRED_VALUE_MISSING", "employee_id"),
        ("REQUIRED_VALUE_MISSING", "quantity"),
    }
    assert all(reason["required"] is True for reason in missing["reasons"])
    assert all("allowed_values" not in reason for reason in missing["reasons"])
    assert all("minimum_value" not in reason for reason in missing["reasons"])
    assert all("maximum_value" not in reason for reason in missing["reasons"])
    draft = next(item for item in body["excluded"] if item["form_id"] == "FORM-DRAFT")
    assert draft["reasons"] == [
        {
            "scope": "FORM",
            "code": "NOT_CONFIRMED",
            "message": "Form is not confirmed.",
        }
    ]
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


def test_finance_and_admin_can_export_empty_filters_and_admin_can_download(
    tmp_path: Path,
) -> None:
    client, services = _build_client(tmp_path)

    finance = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "finance-empty-filters"},
        json={"export_type": "PAYROLL", "filters": {}},
    )
    admin = client.post(
        "/api/v1/exports",
        headers={**ADMIN, "Idempotency-Key": "admin-empty-filters"},
        json={"export_type": "PAYROLL", "filters": {}},
    )
    admin_batch = services.repository.get_export_batch_by_task(admin.json()["task_id"])
    assert admin_batch is not None
    downloaded = client.get(
        f"/api/v1/exports/batches/{admin_batch.export_batch_id}/download",
        headers=ADMIN,
    )

    assert finance.status_code == 202
    assert admin.status_code == 202
    assert downloaded.status_code == 200
    assert downloaded.content == Path(admin_batch.file_path).read_bytes()


def test_export_creation_requires_filters_member(tmp_path: Path) -> None:
    client, _ = _build_client(tmp_path)

    response = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "missing-filters"},
        json={"export_type": "PAYROLL"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"export_type": "PAYROLL", "filters": {"form_idd": "FORM-VALID"}},
        {"export_type": "PAYROLL", "filters": {}, "export_typo": "ignored"},
    ],
)
def test_export_creation_rejects_unknown_body_fields(
    tmp_path: Path,
    body: dict[str, object],
) -> None:
    client, services = _build_client(tmp_path)

    response = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "unknown-body-field"},
        json=body,
    )

    assert response.status_code == 422
    assert services.repository.list_export_batches() == []


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


def test_batch_download_returns_the_exact_bytes_used_for_integrity_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, services = _build_client(tmp_path)
    path = services.settings.exports_root / "snapshot.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"bytes a deferred response would reopen")
    verified_bytes = b"bytes read and verified exactly once"
    services.repository.add_export_batch(
        ExportBatch(
            export_batch_id="EXPORT-SNAPSHOT",
            export_type="PAYROLL",
            filters={},
            included_records=(),
            file_path=str(path),
            file_sha256=sha256(verified_bytes).hexdigest(),
            exported_by="finance-a",
            download_name="../unsafe.xlsx",
        )
    )
    original_read_bytes = Path.read_bytes
    read_count = 0

    def read_verified_snapshot(candidate: Path) -> bytes:
        nonlocal read_count
        if candidate == path:
            read_count += 1
            return verified_bytes
        return original_read_bytes(candidate)

    monkeypatch.setattr(Path, "read_bytes", read_verified_snapshot)

    response = client.get(
        "/api/v1/exports/batches/EXPORT-SNAPSHOT/download",
        headers=FINANCE,
    )

    assert response.status_code == 200
    assert response.content == verified_bytes
    assert read_count == 1
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.headers["content-disposition"] == 'attachment; filename="export.xlsx"'
    assert response.headers["content-length"] == str(len(verified_bytes))


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
    assert task.error == "EXPORT_VALIDATION_FAILED: Export request failed validation."
    assert len(services.repository.list_export_batches()) == 1


def test_failed_export_status_uses_diagnostic_public_error_without_filesystem_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, services = _build_client(tmp_path)
    secret_path = services.settings.exports_root.resolve() / "private-output.xlsx"

    def deny_write(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise PermissionError(13, "filesystem access denied", str(secret_path))

    monkeypatch.setattr(services.exports._exporter, "write", deny_write)

    created = client.post(
        "/api/v1/exports",
        headers={**FINANCE, "Idempotency-Key": "permission-failure"},
        json={"export_type": "PAYROLL", "filters": {"form_id": "FORM-VALID"}},
    )
    status_response = client.get(created.json()["status_url"], headers=FINANCE)

    assert created.status_code == 202
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "FAILED"
    assert status_response.json()["error"] == (
        "EXPORT_STORAGE_ACCESS_FAILED: Export storage is unavailable."
    )
    persisted = services.tasks.get(created.json()["task_id"])
    assert persisted.error == status_response.json()["error"]
    assert str(secret_path) not in status_response.text
    assert "private-output.xlsx" not in status_response.text
    assert "filesystem access denied" not in status_response.text


def test_status_api_replaces_legacy_raw_export_error_with_safe_public_error(
    tmp_path: Path,
) -> None:
    client, services = _build_client(tmp_path)
    secret_path = services.settings.exports_root.resolve() / "legacy-private.xlsx"
    task = services.tasks.submit(
        TaskCommand(
            "XLSX_EXPORT",
            "EXPORTS",
            "finance-a",
            "legacy-raw-error",
            {"export_type": "PAYROLL", "filters": {}},
        )
    )
    services.tasks.start(task.task_id)
    services.tasks.fail(
        task.task_id,
        f"PermissionError: access denied while opening {secret_path}",
    )

    response = client.get(f"/api/v1/tasks/{task.task_id}", headers=FINANCE)

    assert response.status_code == 200
    assert response.json()["error"] == "EXPORT_FAILED: Export could not be completed."
    assert str(secret_path) not in response.text
    assert "legacy-private.xlsx" not in response.text


def test_report_definition_api_lists_six_builtins_and_reads_exact_version(
    tmp_path: Path,
) -> None:
    client, _ = _build_client(tmp_path)

    listed = client.get("/api/v1/exports/report-definitions", headers=FINANCE)
    detail = client.get(
        "/api/v1/exports/report-definitions/PAYROLL_DETAIL:1", headers=FINANCE
    )

    assert listed.status_code == 200
    assert {item["report_key"] for item in listed.json()} == {
        "PAYROLL_DETAIL",
        "EMPLOYEE_PAYROLL_SUMMARY",
        "WORK_ORDER_OUTPUT_SUMMARY",
        "PRODUCT_PROCESS_STATISTICS",
        "WORKSHOP_DAILY",
        "FINANCE_ACCOUNTING",
    }
    assert detail.status_code == 200
    assert detail.json()["kind"] == "DETAIL"
    assert detail.json()["columns"][0] == {
        "source_field": "employee_id",
        "header": "员工编号",
    }


def test_report_definition_api_creates_version_and_rejects_overwrite_or_formula(
    tmp_path: Path,
) -> None:
    client, _ = _build_client(tmp_path)
    body = {
        "definition_id": "CUSTOM_DETAIL:1",
        "report_key": "CUSTOM_DETAIL",
        "version": 1,
        "display_name": "自定义明细",
        "kind": "DETAIL",
        "status": "DRAFT",
        "columns": [{"source_field": "employee_id", "header": "员工编号"}],
        "filters": ["employee_id"],
        "sort_by": ["employee_id"],
        "worksheet": "自定义明细",
    }

    created = client.post(
        "/api/v1/exports/report-definitions", headers=FINANCE, json=body
    )
    repeated = client.post(
        "/api/v1/exports/report-definitions",
        headers=FINANCE,
        json={**body, "definition_id": "CUSTOM_DETAIL:other", "display_name": "覆盖"},
    )
    unsafe = client.post(
        "/api/v1/exports/report-definitions",
        headers=FINANCE,
        json={
            **body,
            "definition_id": "UNSAFE:1",
            "report_key": "UNSAFE",
            "columns": [{"source_field": "quantity * unit_price", "header": "公式"}],
        },
    )

    assert created.status_code == 201
    assert created.json()["definition_id"] == "CUSTOM_DETAIL:1"
    assert repeated.status_code == 409
    assert repeated.json()["code"] == "REPORT_DEFINITION_CONFLICT"
    assert unsafe.status_code == 422
