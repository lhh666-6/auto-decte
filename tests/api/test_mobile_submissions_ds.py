"""Production mobile definition and submission route tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.electronic_forms.models_ds import PresentationConfig, PresentationField
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings


def _services(tmp_path: Path) -> Services:
    services = build_services(Settings(data_root=tmp_path))
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        "E10001",
        "测试员工",
        {},
        "test",
        "fixture",
    )
    services.mobile_identity_repository.set_credential("E10001", "2468")
    services.mobile_identity_repository.set_access_profile(
        "E10001",
        team_id="TEAM-A",
        team_name="测试班组",
        position="操作工",
        roles=["WORKER"],
        allowed_form_types=["SHEET_PIECE_MEASUREMENT"],
        allowed_processes=["CUTTING"],
    )
    definition = services.electronic_definitions.create_draft(
        "SHEET_PIECE_MEASUREMENT",
        "配片数计量考核表",
        template_version_id="TPL-SHEET-V1",
        presentation_config=PresentationConfig(
            fields=[
                PresentationField("block_count", 1, strategy="MANUAL_REQUIRED"),
                PresentationField("pieces_per_block", 2, strategy="DEFAULT_EDITABLE"),
                PresentationField("total_piece_count", 3, strategy="COMPUTED_READ_ONLY"),
            ]
        ),
        created_by="test",
    )
    services.electronic_definitions.publish(definition.definition_version_id)
    return services


def _client(tmp_path: Path) -> tuple[TestClient, str]:
    services = _services(tmp_path)
    client = TestClient(create_app(services))
    login = client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "E10001", "pin": "2468", "device_id": "device-a"},
    )
    assert login.status_code == 200
    definition = services.electronic_definitions.get_published(
        "SHEET_PIECE_MEASUREMENT"
    )
    return client, definition.definition_version_id


def _write_headers(client: TestClient, idempotency_key: str) -> dict[str, str]:
    return {
        "Idempotency-Key": idempotency_key,
        "X-CSRF-Token": client.cookies["mobile_csrf"],
    }


def test_available_forms_and_schema_use_published_authorized_definition(
    tmp_path: Path,
) -> None:
    client, definition_id = _client(tmp_path)

    forms = client.get("/api/v1/mobile/available-forms")
    schema = client.get("/api/v1/mobile/form-schemas/SHEET_PIECE_MEASUREMENT")
    forbidden = client.get("/api/v1/mobile/form-schemas/TEAM_SHEET_PIECE_MEASUREMENT")

    assert forms.status_code == 200
    assert forms.json()["forms"][0]["definition_version_id"] == definition_id
    assert schema.status_code == 200
    assert forbidden.status_code == 403


def test_submission_requires_key_and_server_authoritative_subject(tmp_path: Path) -> None:
    client, definition_id = _client(tmp_path)
    payload = {
        "form_type": "SHEET_PIECE_MEASUREMENT",
        "definition_version_id": definition_id,
        "mode": "SELF",
        "subject_employee_code": "E99999",
        "device_id": "device-a",
        "values": {"block_count": 10, "pieces_per_block": 24},
    }

    assert client.post("/api/v1/mobile/submissions", json=payload).status_code == 400
    forged = client.post(
        "/api/v1/mobile/submissions",
        headers=_write_headers(client, "forged-subject"),
        json=payload,
    )
    assert forged.status_code == 403


def test_submission_requires_matching_csrf_header(tmp_path: Path) -> None:
    client, definition_id = _client(tmp_path)
    response = client.post(
        "/api/v1/mobile/submissions",
        headers={"Idempotency-Key": "missing-csrf"},
        json={
            "form_type": "SHEET_PIECE_MEASUREMENT",
            "definition_version_id": definition_id,
            "mode": "SELF",
            "subject_employee_code": "E10001",
            "device_id": "device-a",
            "values": {"block_count": 10, "pieces_per_block": 24},
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_VALIDATION_FAILED"


def test_submission_rejects_unknown_and_computed_fields(tmp_path: Path) -> None:
    client, definition_id = _client(tmp_path)
    base = {
        "form_type": "SHEET_PIECE_MEASUREMENT",
        "definition_version_id": definition_id,
        "mode": "SELF",
        "subject_employee_code": "E10001",
        "device_id": "device-a",
    }
    unknown = client.post(
        "/api/v1/mobile/submissions",
        headers=_write_headers(client, "unknown"),
        json={**base, "values": {"salary": 999999}},
    )
    computed = client.post(
        "/api/v1/mobile/submissions",
        headers=_write_headers(client, "computed"),
        json={**base, "values": {"total_piece_count": 999999}},
    )

    assert unknown.status_code == 422
    assert computed.status_code == 422


def test_submission_is_idempotent_and_conflicts_on_different_payload(
    tmp_path: Path,
) -> None:
    client, definition_id = _client(tmp_path)
    base = {
        "form_type": "SHEET_PIECE_MEASUREMENT",
        "definition_version_id": definition_id,
        "mode": "SELF",
        "subject_employee_code": "E10001",
        "device_id": "device-a",
    }
    headers = _write_headers(client, "same-operation")
    first = client.post(
        "/api/v1/mobile/submissions",
        headers=headers,
        json={**base, "values": {"block_count": 10, "pieces_per_block": 24}},
    )
    replay = client.post(
        "/api/v1/mobile/submissions",
        headers=headers,
        json={**base, "values": {"block_count": 10, "pieces_per_block": 24}},
    )
    conflict = client.post(
        "/api/v1/mobile/submissions",
        headers=headers,
        json={**base, "values": {"block_count": 11, "pieces_per_block": 24}},
    )

    assert first.status_code == 200
    assert replay.json()["submission_id"] == first.json()["submission_id"]
    assert conflict.status_code == 409

    listed = client.get("/api/v1/mobile/submissions")
    assert listed.status_code == 200
    assert listed.json()["submissions"][0]["submission_id"] == first.json()["submission_id"]
    assert listed.json()["submissions"][0]["form_id"]


def test_mobile_context_uses_master_data_and_team_profiles(tmp_path: Path) -> None:
    services = _services(tmp_path)
    services.master_data.create(
        MasterDataCatalog.WORK_ORDERS,
        "WO-100",
        "测试工单",
        {},
        "test",
        "fixture",
    )
    services.master_data.create(
        MasterDataCatalog.PRODUCTS,
        "P-100",
        "测试产品",
        {"spec": "10x20", "pieces_per_block": 24},
        "test",
        "fixture",
    )
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        "E10002",
        "同组员工",
        {},
        "test",
        "fixture",
    )
    services.mobile_identity_repository.set_access_profile(
        "E10002",
        team_id="TEAM-A",
        team_name="测试班组",
        position="操作工",
        roles=["WORKER"],
        allowed_form_types=["SHEET_PIECE_MEASUREMENT"],
        allowed_processes=["CUTTING"],
    )
    client = TestClient(create_app(services))
    assert client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "E10001", "pin": "2468", "device_id": "device-a"},
    ).status_code == 200

    context = client.get("/api/v1/mobile/production-contexts/current")
    members = client.get("/api/v1/mobile/team-members")

    assert context.status_code == 200
    assert context.json()["work_orders"] == ["WO-100"]
    assert context.json()["products"] == ["P-100"]
    assert context.json()["specs"] == ["10x20"]
    assert context.json()["pieces_per_block"] == 24
    assert {member["employee_code"] for member in members.json()["members"]} == {
        "E10001",
        "E10002",
    }


def test_team_leader_cannot_submit_for_employee_outside_team(tmp_path: Path) -> None:
    services = _services(tmp_path)
    services.mobile_identity_repository.set_access_profile(
        "E10001",
        team_id="TEAM-A",
        team_name="测试班组",
        position="班组长",
        roles=["TEAM_LEADER"],
        allowed_form_types=["TEAM_SHEET_PIECE_MEASUREMENT"],
        allowed_processes=["CUTTING"],
    )
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        "E20001",
        "其他班组员工",
        {},
        "test",
        "fixture",
    )
    services.mobile_identity_repository.set_access_profile(
        "E20001",
        team_id="TEAM-B",
        team_name="其他班组",
        position="操作工",
        roles=["WORKER"],
        allowed_form_types=[],
        allowed_processes=[],
    )
    definition = services.electronic_definitions.create_draft(
        "TEAM_SHEET_PIECE_MEASUREMENT",
        "班组配片记录",
        template_version_id="TPL-TEAM-V1",
        presentation_config=PresentationConfig(
            fields=[PresentationField("block_count", 1, strategy="MANUAL_REQUIRED")]
        ),
        created_by="test",
    )
    services.electronic_definitions.publish(definition.definition_version_id)
    client = TestClient(create_app(services))
    assert client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "E10001", "pin": "2468", "device_id": "device-a"},
    ).status_code == 200

    response = client.post(
        "/api/v1/mobile/submissions",
        headers=_write_headers(client, "outside-team"),
        json={
            "form_type": "TEAM_SHEET_PIECE_MEASUREMENT",
            "definition_version_id": definition.definition_version_id,
            "mode": "TEAM_LEADER_BATCH",
            "subject_employee_code": "E20001",
            "device_id": "device-a",
            "values": {"block_count": 10},
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "SUBJECT_NOT_IN_TEAM"
