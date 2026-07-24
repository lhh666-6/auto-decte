"""P0-1: Plant manager Web production visibility — directed tests.

Prove: GET /api/v1/plant/production returns ALL factory records
regardless of stage, enforces cross-factory isolation, and the
mobile bamboo boundary remains intact (403 PLANT_MANAGER_WEB_ONLY).
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings


def _add_user(services: Services, code: str, role: str, factory_id: str, factory_name: str) -> None:
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES, code, code, {}, "p0-1-test", "shared fixture",
    )
    services.mobile_identity_repository.set_credential(code, "2468")
    services.mobile_identity_repository.set_access_profile(
        code,
        team_id=f"TEAM-{factory_id}",
        team_name=f"{factory_name}生产组",
        position=role,
        roles=[role],
        allowed_form_types=[],
        allowed_processes=["BAMBOO_PROCESS"],
        factory_id=factory_id,
        factory_name=factory_name,
        bamboo_role=role,
    )


def _mobile(services: Services, code: str) -> TestClient:
    client = TestClient(create_app(services))
    resp = client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": code, "pin": "2468", "device_id": f"{code}-phone"},
    )
    assert resp.status_code == 200
    return client


def _web(services: Services, code: str) -> TestClient:
    client = TestClient(create_app(services))
    resp = client.post(
        "/api/v1/web/auth/login",
        json={"employee_code": code, "pin": "2468", "device_id": f"{code}-browser"},
    )
    assert resp.status_code == 200
    return client


# ── TEST P0-1-A: sees all factory records regardless of stage ──
def test_plant_manager_sees_factory_records_at_sort_stage(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "SORT-A", "SORT_OPERATOR", "FACTORY-A", "测试一厂")
    _add_user(services, "PM-A", "PLANT_MANAGER", "FACTORY-A", "测试一厂")

    # Sort operator creates a record
    mobile = _mobile(services, "SORT-A")
    created = mobile.post(
        "/api/v1/mobile/bamboo/records",
        headers={
            "X-CSRF-Token": mobile.cookies["mobile_csrf"],
            "Idempotency-Key": "p0-1-a-create",
        },
        json={
            "base_info": {
                "mode": "分选", "cage_no": "P0-1-A",
                "length": "2.3", "shade": "深", "grade": "A",
                "bundle_count": 10,
            },
        },
    )
    assert created.status_code == 201
    record_id = created.json()["record_id"]

    # Plant manager queries Web production list
    web = _web(services, "PM-A")
    resp = web.get("/api/v1/plant/production")
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    visible_ids = {r["record_id"] for r in data["records"]}
    assert record_id in visible_ids, f"SORT-stage record missing: visible={visible_ids}"
    # Verify the record is at SORT (not PLANT_AUDIT)
    for r in data["records"]:
        if r["record_id"] == record_id:
            assert r.get("current_stage") in (None, "SORT"), (
                f"Expected SORT stage, got {r.get('current_stage')}"
            )

    services.engine.dispose()


# ── TEST P0-1-B: cross-factory isolation ──
def test_plant_manager_cannot_see_other_factory_records(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "SORT-A", "SORT_OPERATOR", "FACTORY-A", "测试一厂")
    _add_user(services, "SORT-B", "SORT_OPERATOR", "FACTORY-B", "测试二厂")
    _add_user(services, "PM-A", "PLANT_MANAGER", "FACTORY-A", "测试一厂")

    mobile_a = _mobile(services, "SORT-A")
    created_a = mobile_a.post(
        "/api/v1/mobile/bamboo/records",
        headers={"X-CSRF-Token": mobile_a.cookies["mobile_csrf"], "Idempotency-Key": "p0-1-b-a"},
        json={"base_info": {"mode": "分选", "cage_no": "CAGE-FA", "length": "2.3", "shade": "深", "grade": "A", "bundle_count": 10}},  # noqa: E501  # noqa: E501
    )
    assert created_a.status_code == 201
    record_a = created_a.json()["record_id"]

    mobile_b = _mobile(services, "SORT-B")
    created_b = mobile_b.post(
        "/api/v1/mobile/bamboo/records",
        headers={"X-CSRF-Token": mobile_b.cookies["mobile_csrf"], "Idempotency-Key": "p0-1-b-b"},
        json={"base_info": {"mode": "分选", "cage_no": "CAGE-FB", "length": "2.3", "shade": "深", "grade": "A", "bundle_count": 10}},  # noqa: E501  # noqa: E501
    )
    assert created_b.status_code == 201
    record_b = created_b.json()["record_id"]

    web = _web(services, "PM-A")
    resp = web.get("/api/v1/plant/production")
    visible_ids = {r["record_id"] for r in resp.json()["records"]}
    assert record_a in visible_ids, "Factory A record should be visible"
    assert record_b not in visible_ids, "Factory B record must NOT be visible"

    services.engine.dispose()


# ── TEST P0-1-C: production list is not PLANT_AUDIT-only ──
def test_production_list_is_not_task_stage_scoped(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "SORT-A", "SORT_OPERATOR", "FACTORY-A", "测试一厂")
    _add_user(services, "PM-A", "PLANT_MANAGER", "FACTORY-A", "测试一厂")

    mobile = _mobile(services, "SORT-A")
    created = mobile.post(
        "/api/v1/mobile/bamboo/records",
        headers={"X-CSRF-Token": mobile.cookies["mobile_csrf"], "Idempotency-Key": "p0-1-c"},
        json={"base_info": {"mode": "分选", "cage_no": "CAGE-C", "length": "2.3", "shade": "深", "grade": "A", "bundle_count": 10}},  # noqa: E501
    )
    assert created.status_code == 201
    record_id = created.json()["record_id"]
    stage = created.json().get("current_stage")
    assert stage != "PLANT_AUDIT", f"Expected non-PLANT_AUDIT stage, got {stage}"

    web = _web(services, "PM-A")
    resp = web.get("/api/v1/plant/production")
    assert record_id in {r["record_id"] for r in resp.json()["records"]}, (
        "SORT-stage record should be visible, but it's missing"
    )

    services.engine.dispose()


# ── TEST P0-1-D: mobile bamboo blocks PLANT_MANAGER ──
def test_plant_manager_mobile_bamboo_remains_web_only(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "PM-A", "PLANT_MANAGER", "FACTORY-A", "测试一厂")

    mobile = _mobile(services, "PM-A")
    resp = mobile.get("/api/v1/mobile/bamboo/dashboard")
    assert resp.status_code == 403
    assert resp.json()["code"] == "PLANT_MANAGER_WEB_ONLY"

    services.engine.dispose()


# ── TEST P0-1-E: factory_id consistency ──
def test_factory_identity_matches_record_factory(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "SORT-A", "SORT_OPERATOR", "FACTORY-A", "测试一厂")
    _add_user(services, "PM-A", "PLANT_MANAGER", "FACTORY-A", "测试一厂")

    mobile = _mobile(services, "SORT-A")
    created = mobile.post(
        "/api/v1/mobile/bamboo/records",
        headers={"X-CSRF-Token": mobile.cookies["mobile_csrf"], "Idempotency-Key": "p0-1-e"},
        json={"base_info": {"mode": "分选", "cage_no": "CAGE-E", "length": "2.3", "shade": "深", "grade": "A", "bundle_count": 10}},  # noqa: E501
    )
    assert created.status_code == 201
    record_factory = created.json()["factory_id"]

    # Plant manager's resolved factory
    web = _web(services, "PM-A")
    resp = web.get("/api/v1/plant/production")
    for r in resp.json()["records"]:
        assert r["factory_id"] == "FACTORY-A", (
            f"record {r['record_id']} factory={r['factory_id']!r}, expected FACTORY-A"
        )
    assert record_factory == "FACTORY-A"

    services.engine.dispose()
