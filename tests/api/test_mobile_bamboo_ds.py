from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings


def _add_bamboo_user(
    services: Services,
    *,
    employee_code: str,
    role: str,
    factory_id: str = "FACTORY-A",
) -> None:
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        employee_code,
        employee_code,
        {},
        "test",
        "bamboo API fixture",
    )
    services.mobile_identity_repository.set_credential(employee_code, "2468")
    services.mobile_identity_repository.set_access_profile(
        employee_code,
        team_id=f"TEAM-{factory_id}",
        team_name=f"{factory_id}班组",
        position=role,
        roles=["WORKER"],
        allowed_form_types=[],
        allowed_processes=["BAMBOO_PROCESS"],
        factory_id=factory_id,
        factory_name=factory_id,
        bamboo_role=role,
    )


def _client(services: Services, employee_code: str) -> TestClient:
    client = TestClient(create_app(services))
    response = client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": employee_code, "pin": "2468", "device_id": "phone"},
    )
    assert response.status_code == 200
    return client


def _write_headers(client: TestClient, key: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies["mobile_csrf"],
        "Idempotency-Key": key,
    }


def test_bamboo_record_opens_to_each_role_only_after_previous_signature(
    tmp_path: Path,
) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_bamboo_user(services, employee_code="E-SORT", role="SORT_OPERATOR")
    _add_bamboo_user(services, employee_code="E-DIP", role="DIPPING_OPERATOR")
    _add_bamboo_user(services, employee_code="E-DRY", role="DRYING_RACK_OPERATOR")
    sort_client = _client(services, "E-SORT")
    dipping_client = _client(services, "E-DIP")
    drying_client = _client(services, "E-DRY")

    created = sort_client.post(
        "/api/v1/mobile/bamboo/records",
        headers=_write_headers(sort_client, "create-1"),
        json={
            "base_info": {
                "cage_no": "3-018",
                "length": "2.3",
                "grade": "A",
                "bundle_count": 16,
            }
        },
    )
    assert created.status_code == 201
    record_id = created.json()["record_id"]
    assert created.json()["current_stage"] == "SORT"
    repeated = sort_client.post(
        "/api/v1/mobile/bamboo/records",
        headers=_write_headers(sort_client, "create-1"),
        json={"base_info": {"ignored_on_retry": True}},
    )
    assert repeated.json()["record_id"] == record_id
    assert sort_client.get("/api/v1/mobile/bamboo/dashboard").json()["available"] == 1
    assert drying_client.get(
        f"/api/v1/mobile/bamboo/records/{record_id}"
    ).status_code == 404

    wrong_stage = sort_client.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/stages/DIPPING/submit",
        headers=_write_headers(sort_client, "wrong-stage"),
        json={"expected_revision": 1, "device_id": "sort-phone", "values": {}},
    )
    assert wrong_stage.status_code == 409
    assert wrong_stage.json()["code"] == "STAGE_NOT_AVAILABLE"
    stale = sort_client.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit",
        headers=_write_headers(sort_client, "stale-stage"),
        json={"expected_revision": 99, "device_id": "sort-phone", "values": {}},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_REVISION"

    signed = sort_client.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit",
        headers=_write_headers(sort_client, "sort-1"),
        json={
            "expected_revision": 1,
            "device_id": "sort-phone",
            "values": {"moisture": [12, 13]},
        },
    )
    assert signed.status_code == 200
    assert signed.json()["current_stage"] == "DIPPING"
    assert dipping_client.get(
        f"/api/v1/mobile/bamboo/records/{record_id}"
    ).status_code == 200
    assert drying_client.get(
        f"/api/v1/mobile/bamboo/records/{record_id}"
    ).status_code == 404
    assert dipping_client.get(
        "/api/v1/mobile/bamboo/dashboard"
    ).json()["available"] == 1


def test_bamboo_writes_require_csrf_and_idempotency_key(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_bamboo_user(services, employee_code="E-SORT", role="SORT_OPERATOR")
    client = _client(services, "E-SORT")

    missing_key = client.post(
        "/api/v1/mobile/bamboo/records",
        headers={"X-CSRF-Token": client.cookies["mobile_csrf"]},
        json={"base_info": {}},
    )
    assert missing_key.status_code == 400
    assert missing_key.json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    missing_csrf = client.post(
        "/api/v1/mobile/bamboo/records",
        headers={"Idempotency-Key": "create-1"},
        json={"base_info": {}},
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_VALIDATION_FAILED"


def test_cross_factory_record_is_not_visible(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_bamboo_user(services, employee_code="E-SORT-A", role="SORT_OPERATOR")
    _add_bamboo_user(
        services,
        employee_code="E-SORT-B",
        role="SORT_OPERATOR",
        factory_id="FACTORY-B",
    )
    factory_a = _client(services, "E-SORT-A")
    factory_b = _client(services, "E-SORT-B")
    created = factory_a.post(
        "/api/v1/mobile/bamboo/records",
        headers=_write_headers(factory_a, "create-a"),
        json={"base_info": {}},
    )

    response = factory_b.get(
        f"/api/v1/mobile/bamboo/records/{created.json()['record_id']}"
    )

    assert response.status_code == 404
    assert response.json()["code"] == "RECORD_NOT_VISIBLE"
    submit = factory_b.post(
        f"/api/v1/mobile/bamboo/records/{created.json()['record_id']}/stages/SORT/submit",
        headers=_write_headers(factory_b, "cross-factory"),
        json={"expected_revision": 1, "device_id": "phone-b", "values": {}},
    )
    assert submit.status_code == 404
    assert submit.json()["code"] == "RECORD_NOT_VISIBLE"
