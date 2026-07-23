"""Plant Web must expose the same Bamboo records and notifications."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.adapters.database.models import MobileNotificationRow
from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings


def _add_user(services: Services, code: str, role: str) -> None:
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        code,
        code,
        {},
        "plant-web-test",
        "shared bamboo fixture",
    )
    services.mobile_identity_repository.set_credential(code, "2468")
    services.mobile_identity_repository.set_access_profile(
        code,
        team_id="TEAM-A",
        team_name="竹丝一厂",
        position=role,
        roles=[role],
        allowed_form_types=[],
        allowed_processes=["BAMBOO_PROCESS"],
        factory_id="FACTORY-A",
        factory_name="竹丝一厂",
        bamboo_role=role,
    )


def _mobile(services: Services, code: str) -> TestClient:
    client = TestClient(create_app(services))
    response = client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": code, "pin": "2468", "device_id": f"{code}-phone"},
    )
    assert response.status_code == 200
    return client


def _web(services: Services, code: str) -> TestClient:
    client = TestClient(create_app(services))
    response = client.post(
        "/api/v1/web/auth/login",
        json={"employee_code": code, "pin": "2468", "device_id": f"{code}-browser"},
    )
    assert response.status_code == 200
    return client


def test_plant_web_reads_shared_bamboo_records_and_notifications(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "SORT-1", "SORT_OPERATOR")
    _add_user(services, "MANAGER-1", "PLANT_MANAGER")
    sort = _mobile(services, "SORT-1")
    created = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers={
            "X-CSRF-Token": sort.cookies["mobile_csrf"],
            "Idempotency-Key": "plant-web-shared-record",
        },
        json={
            "base_info": {
                "cage_no": "WEB-SHARED-01",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 8,
            }
        },
    )
    assert created.status_code == 201
    record_id = created.json()["record_id"]
    with Session(services.engine) as session, session.begin():
        session.add(
            MobileNotificationRow(
                notification_id="NOTICE-SHARED-1",
                recipient_actor_id="MANAGER-1",
                category="PRODUCTION",
                title="生产记录待处理",
                body="请查看同一条竹丝生产记录。",
                link=f"/plant/production/{record_id}",
                payload={"record_id": record_id},
                read_at=None,
                created_at=datetime.now(UTC),
            )
        )

    manager = _web(services, "MANAGER-1")
    production = manager.get("/api/v1/plant/production")
    notifications = manager.get("/api/v1/plant/notifications")

    assert production.status_code == 200
    assert [item["record_id"] for item in production.json()["records"]] == [record_id]
    assert notifications.status_code == 200
    assert notifications.json()["items"][0]["notification_id"] == "NOTICE-SHARED-1"

    read = manager.post(
        "/api/v1/plant/notifications/NOTICE-SHARED-1/acknowledge",
        headers={"X-CSRF-Token": manager.cookies["web_csrf"]},
    )
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    with Session(services.engine) as session:
        assert session.get(MobileNotificationRow, "NOTICE-SHARED-1").read_at is not None

    revision = production.json()["records"][0]["revision"]
    return_headers = {
        "X-CSRF-Token": manager.cookies["web_csrf"],
        "Idempotency-Key": "plant-return-shared-record",
    }
    returned = manager.post(
        f"/api/v1/plant/records/{record_id}/return",
        headers=return_headers,
        json={
            "target_stages": ["SORT"],
            "reason": "厂长选择退回分选重做",
            "expected_revision": revision,
        },
    )
    replay = manager.post(
        f"/api/v1/plant/records/{record_id}/return",
        headers=return_headers,
        json={
            "target_stages": ["SORT"],
            "reason": "厂长选择退回分选重做",
            "expected_revision": revision,
        },
    )
    stale = manager.post(
        f"/api/v1/plant/records/{record_id}/return",
        headers={
            "X-CSRF-Token": manager.cookies["web_csrf"],
            "Idempotency-Key": "plant-return-stale",
        },
        json={
            "target_stages": ["SORT"],
            "reason": "旧页面重复操作",
            "expected_revision": revision,
        },
    )
    assert returned.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == returned.json()
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"

    manager_mobile = _mobile(services, "MANAGER-1")
    mobile_dashboard = manager_mobile.get("/api/v1/mobile/bamboo/dashboard")
    assert mobile_dashboard.status_code == 403
    assert mobile_dashboard.json()["code"] == "PLANT_MANAGER_WEB_ONLY"


def test_two_plant_web_returns_cannot_both_commit(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "SORT-1", "SORT_OPERATOR")
    _add_user(services, "MANAGER-1", "PLANT_MANAGER")
    sort = _mobile(services, "SORT-1")
    created = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers={
            "X-CSRF-Token": sort.cookies["mobile_csrf"],
            "Idempotency-Key": "concurrent-record",
        },
        json={
            "base_info": {
                "cage_no": "CONCURRENT-01",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 8,
            }
        },
    ).json()
    first = _web(services, "MANAGER-1")
    second = _web(services, "MANAGER-1")

    def submit(client: TestClient, key: str) -> tuple[int, str]:
        response = client.post(
            f"/api/v1/plant/records/{created['record_id']}/return",
            headers={
                "X-CSRF-Token": client.cookies["web_csrf"],
                "Idempotency-Key": key,
            },
            json={
                "target_stages": ["SORT"],
                "reason": key,
                "expected_revision": created["revision"],
            },
        )
        return response.status_code, response.json().get("code", "")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda args: submit(*args),
            [(first, "concurrent-a"), (second, "concurrent-b")],
        ))

    assert sorted(status for status, _ in results) == [200, 409]
    assert "REVISION_CONFLICT" in {code for _, code in results}


def test_plant_signature_detail_exposes_mobile_audit_context(tmp_path: Path) -> None:
    services = build_services(
        Settings(data_root=tmp_path, bamboo_plant_audit_wait_hours=0)
    )
    _add_user(services, "SORT-1", "SORT_OPERATOR")
    _add_user(services, "SUP-1", "SUPERVISOR")
    _add_user(services, "MANAGER-1", "PLANT_MANAGER")
    sort = _mobile(services, "SORT-1")
    supervisor = _mobile(services, "SUP-1")
    manager = _web(services, "MANAGER-1")

    created = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers={
            "X-CSRF-Token": sort.cookies["mobile_csrf"],
            "Idempotency-Key": "signature-detail-create",
        },
        json={
            "base_info": {
                "cage_no": "SIGN-01",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 8,
            }
        },
    ).json()
    record_id = created["record_id"]
    sort.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit",
        headers={
            "X-CSRF-Token": sort.cookies["mobile_csrf"],
            "Idempotency-Key": "signature-detail-sort",
        },
        json={
            "expected_revision": 1,
            "device_id": "sort-phone",
            "values": {"moisture": [12], "note": "分选正常"},
        },
    ).raise_for_status()
    supervisor.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/stages/SUPERVISOR/submit",
        headers={
            "X-CSRF-Token": supervisor.cookies["mobile_csrf"],
            "Idempotency-Key": "signature-detail-supervisor",
        },
        json={
            "expected_revision": 2,
            "device_id": "supervisor-phone",
            "values": {"result": "APPROVED", "note": "主管已核对"},
        },
    ).raise_for_status()

    detail = manager.get(f"/api/v1/plant/production/{record_id}")

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["current_stage"] == "PLANT_AUDIT"
    assert [item["stage"] for item in payload["submissions"]] == [
        "SORT",
        "SUPERVISOR",
    ]
    assert payload["inspection_window"]["status"] == "OPEN"
    assert payload["signature_gate"]["can_sign"] is False
    assert payload["signature_gate"]["reason"] == "INSPECTION_IN_PROGRESS"
