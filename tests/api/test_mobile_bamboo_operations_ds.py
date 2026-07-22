from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings


def _add_user(services: Services, code: str, role: str) -> None:
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES, code, code, {}, "test", "bamboo operations"
    )
    services.mobile_identity_repository.set_credential(code, "2468")
    services.mobile_identity_repository.set_access_profile(
        code,
        team_id="TEAM-A",
        team_name="一厂",
        position=role,
        roles=["WORKER"],
        allowed_form_types=[],
        allowed_processes=["BAMBOO_PROCESS"],
        factory_id="FACTORY-A",
        factory_name="竹丝一厂",
        bamboo_role=role,
    )


def _client(services: Services, code: str) -> TestClient:
    client = TestClient(create_app(services))
    result = client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": code, "pin": "2468", "device_id": f"{code}-phone"},
    )
    assert result.status_code == 200
    return client


def _headers(client: TestClient, key: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies["mobile_csrf"],
        "Idempotency-Key": key,
    }


def _submit(
    client: TestClient,
    record_id: str,
    stage: str,
    revision: int,
    values: dict[str, object],
) -> dict[str, object]:
    result = client.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/stages/{stage}/submit",
        headers=_headers(client, f"{record_id}-{stage}-{revision}"),
        json={"expected_revision": revision, "device_id": "phone", "values": values},
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_complete_bamboo_operations_from_payroll_through_finance(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path, bamboo_plant_audit_wait_hours=0))
    for code, role in (
        ("SORT-1", "SORT_OPERATOR"),
        ("DIP-1", "DIPPING_OPERATOR"),
        ("DRY-1", "DRYING_RACK_OPERATOR"),
        ("INSPECT-1", "INSPECTOR"),
        ("SUP-1", "SUPERVISOR"),
        ("MANAGER-1", "PLANT_MANAGER"),
        ("FIN-1", "FINANCE_APPROVER"),
    ):
        _add_user(services, code, role)

    sort = _client(services, "SORT-1")
    dipping = _client(services, "DIP-1")
    drying = _client(services, "DRY-1")
    inspector = _client(services, "INSPECT-1")
    supervisor = _client(services, "SUP-1")
    manager = _client(services, "MANAGER-1")
    finance = _client(services, "FIN-1")

    created = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers=_headers(sort, "create-complete"),
        json={
            "base_info": {
                "cage_no": "L-207",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 10,
            }
        },
    ).json()
    sorting_id = str(created["record_id"])
    sorted_record = _submit(
        sort,
        sorting_id,
        "SORT",
        1,
        {"moisture": [12, 13, 14], "wage_amount": "80"},
    )
    assert sorted_record["current_stage"] == "SUPERVISOR"
    linked_tasks = dipping.get("/api/v1/mobile/bamboo/tasks").json()["tasks"]
    assert len(linked_tasks) == 1
    linked_id = str(linked_tasks[0]["record_id"])
    assert linked_tasks[0]["source_record_id"] == sorting_id
    _submit(
        dipping,
        linked_id,
        "DIPPING",
        1,
        {"moisture": [11, 12, 13], "wage_amount": "30"},
    )
    _submit(
        drying,
        linked_id,
        "DRYING",
        2,
        {
            "moisture": [8, 9, 10],
            "rack_numbers": ["R-01", "R-02"],
            "wage_amount": "20",
        },
    )

    inspection = inspector.post(
        f"/api/v1/mobile/bamboo/records/{linked_id}/inspections",
        headers=_headers(inspector, "inspect-1"),
        json={
            "serial_no": "JC-001",
            "target_stage": "DRYING",
            "moisture_points": [12.0, 13.0, 14.0],
            "conclusion": "NONCONFORMING",
            "note": "含水率偏高",
            "text_evidence": "现场复测并留痕",
            "device_id": "inspect-phone",
        },
    )
    assert inspection.status_code == 201
    payload = inspection.json()
    assert payload["average_value"] == "13.00"
    assert payload["evidence"][0]["evidence_type"] == "TEXT"
    exception_id = payload["exception"]["exception_id"]

    blocked = supervisor.post(
        f"/api/v1/mobile/bamboo/records/{linked_id}/stages/SUPERVISOR/submit",
        headers=_headers(supervisor, "supervisor-blocked"),
        json={"expected_revision": 3, "device_id": "phone", "values": {}},
    )
    assert blocked.status_code == 409
    inspector.post(
        f"/api/v1/mobile/bamboo/inspection-exceptions/{exception_id}/close",
        headers=_headers(inspector, "close-exception"),
        json={"resolution": "复测合格"},
    ).raise_for_status()

    _submit(supervisor, linked_id, "SUPERVISOR", 3, {"result": "APPROVED"})
    linked_audit = _submit(
        manager,
        linked_id,
        "PLANT_AUDIT",
        4,
        {"result": "APPROVED"},
    )
    _submit(supervisor, sorting_id, "SUPERVISOR", 2, {"result": "APPROVED"})
    sorting_audit = _submit(
        manager,
        sorting_id,
        "PLANT_AUDIT",
        3,
        {"result": "APPROVED"},
    )
    assert linked_audit["status"] == "COMPLETED"
    assert sorting_audit["status"] == "COMPLETED"

    sorting_operations = manager.get(
        f"/api/v1/mobile/bamboo/records/{sorting_id}/operations"
    ).json()
    linked_operations = manager.get(
        f"/api/v1/mobile/bamboo/records/{linked_id}/operations"
    ).json()
    assert [fact["fact_type"] for fact in sorting_operations["payroll_facts"]] == [
        "SORT"
    ]
    assert [fact["fact_type"] for fact in linked_operations["payroll_facts"]] == [
        "DIPPING_DRYING_JOINT"
    ]
    assert sorting_operations["payroll_facts"][0]["status"] == "EFFECTIVE"
    assert linked_operations["payroll_facts"][0]["status"] == "EFFECTIVE"

    batches = finance.get("/api/v1/mobile/bamboo/finance/daily-batches").json()
    assert len(batches) == 1
    assert sorted(item["amount"] for item in batches[0]["items"]) == ["20.00", "30.00", "80.00"]
    inquiry = finance.post(
        f"/api/v1/mobile/bamboo/finance/items/{batches[0]['items'][0]['item_id']}/inquiries",
        headers=_headers(finance, "ask-manager"),
        json={"subject": "核对工资来源", "body": "请说明原始表单情况"},
    )
    assert inquiry.status_code == 201
    inquiry_id = inquiry.json()["inquiry_id"]
    manager_inquiries = manager.get("/api/v1/mobile/bamboo/finance/inquiries").json()
    assert manager_inquiries[0]["messages"][0]["body"] == "请说明原始表单情况"
    manager.post(
        f"/api/v1/mobile/bamboo/finance/inquiries/{inquiry_id}/reply",
        headers=_headers(manager, "manager-reply"),
        json={"body": "已查原始表单，数据属实", "close": False},
    ).raise_for_status()
    for index, item in enumerate(batches[0]["items"]):
        approved = finance.post(
            f"/api/v1/mobile/bamboo/finance/items/{item['item_id']}/decision",
            headers=_headers(finance, f"approve-{index}"),
            json={"decision": "APPROVED", "note": "核对通过"},
        )
        assert approved.status_code == 200

    month = datetime.now().strftime("%Y-%m")
    summary = finance.get(
        "/api/v1/mobile/bamboo/finance/monthly-summary", params={"month": month}
    ).json()
    assert summary["total_amount"] == "130.00"
    exported = finance.get("/api/v1/mobile/bamboo/finance/export.xlsx", params={"month": month})
    assert exported.status_code == 200
    assert exported.content.startswith(b"PK")

    correction_item = next(item for item in batches[0]["items"] if item["employee_code"] == "DRY-1")
    correction = finance.post(
        f"/api/v1/mobile/bamboo/finance/items/{correction_item['item_id']}/decision",
        headers=_headers(finance, "require-correction"),
        json={"decision": "CORRECTION_REQUIRED", "note": "干燥数据需重写"},
    )
    assert correction.status_code == 200
    returned = supervisor.post(
        f"/api/v1/mobile/bamboo/records/{linked_id}/return",
        headers=_headers(supervisor, "return-drying"),
        json={
            "target_stages": ["DRYING"],
            "reason": "主管判定干燥环节需要重写",
            "source": "FINANCE",
        },
    )
    assert returned.status_code == 200
    assert returned.json()["current_stage"] == "DRYING"
    _submit(
        drying,
        linked_id,
        "DRYING",
        6,
        {
            "moisture": [7, 8, 9],
            "rack_numbers": ["R-03", "R-04"],
            "wage_amount": "22",
        },
    )
    _submit(supervisor, linked_id, "SUPERVISOR", 7, {"result": "APPROVED"})
    _submit(manager, linked_id, "PLANT_AUDIT", 8, {"result": "APPROVED"})
    supplemented = finance.get("/api/v1/mobile/bamboo/finance/daily-batches").json()
    assert len(supplemented) == 2
    assert any(batch["supplemental"] for batch in supplemented)


def test_returning_sorting_marks_linked_source_snapshot_upstream_changed(
    tmp_path: Path,
) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "SORT-1", "SORT_OPERATOR")
    _add_user(services, "DIP-1", "DIPPING_OPERATOR")
    _add_user(services, "SUP-1", "SUPERVISOR")
    sort = _client(services, "SORT-1")
    dipping = _client(services, "DIP-1")
    supervisor = _client(services, "SUP-1")

    created = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers=_headers(sort, "create-return"),
        json={
            "base_info": {
                "cage_no": "RETURN-1",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 10,
            }
        },
    ).json()
    sorting_id = str(created["record_id"])
    _submit(sort, sorting_id, "SORT", 1, {"moisture": [12, 13, 14]})
    linked = dipping.get("/api/v1/mobile/bamboo/tasks").json()["tasks"][0]

    returned = supervisor.post(
        f"/api/v1/mobile/bamboo/records/{sorting_id}/return",
        headers=_headers(supervisor, "return-sorting"),
        json={
            "target_stages": ["SORT"],
            "reason": "分选数据需要重填",
            "source": "SUPERVISOR",
        },
    )

    assert returned.status_code == 200
    assert returned.json()["current_stage"] == "SORT"
    refreshed_linked = dipping.get(
        f"/api/v1/mobile/bamboo/records/{linked['record_id']}"
    ).json()
    snapshot = refreshed_linked["source_snapshot"]
    assert snapshot["source_status"] == "UPSTREAM_CHANGED"
    assert snapshot["original_revision"] == 2
    assert snapshot["latest_revision"] == 3


def test_worker_role_change_requires_factory_manager_approval(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "SORT-1", "SORT_OPERATOR")
    _add_user(services, "MANAGER-1", "PLANT_MANAGER")
    worker = _client(services, "SORT-1")
    manager = _client(services, "MANAGER-1")

    requested = worker.post(
        "/api/v1/mobile/bamboo/role-change-requests",
        headers=_headers(worker, "role-change"),
        json={"to_role": "DIPPING_OPERATOR", "reason": "转岗培训已完成"},
    )
    assert requested.status_code == 201
    request_id = requested.json()["request_id"]
    listed = manager.get("/api/v1/mobile/bamboo/role-change-requests").json()
    assert listed[0]["status"] == "PENDING"
    decision = manager.post(
        f"/api/v1/mobile/bamboo/role-change-requests/{request_id}/decision",
        headers=_headers(manager, "approve-role-change"),
        json={"approve": True, "note": "同意"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "APPROVED"

    refreshed = _client(services, "SORT-1")
    me = refreshed.get("/api/v1/mobile/auth/session").json()
    assert me["bamboo_role"] == "DIPPING_OPERATOR"


def test_manager_configures_factory_rule_and_assigns_new_hire(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "MANAGER-1", "PLANT_MANAGER")
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        "NEW-1",
        "新员工",
        {},
        "test",
        "pending role",
    )
    services.mobile_identity_repository.set_credential("NEW-1", "2468")
    manager = _client(services, "MANAGER-1")

    rule = manager.post(
        "/api/v1/mobile/bamboo/payroll-rules",
        headers=_headers(manager, "factory-rule"),
        json={
            "rule_key": "SORT",
            "configuration": {
                "unit_rate": "1.20",
                "length_multipliers": {"2.3": "6"},
            },
            "system_default": False,
        },
    )
    assert rule.status_code == 201
    assert rule.json()["factory_id"] == "FACTORY-A"
    assert rule.json()["version"] == 1

    assigned = manager.post(
        "/api/v1/mobile/bamboo/admin/assignments",
        headers=_headers(manager, "assign-new-hire"),
        json={"employee_code": "NEW-1", "role_code": "INSPECTOR"},
    )
    assert assigned.status_code == 201
    assert assigned.json()["role_code"] == "INSPECTOR"
    new_hire = _client(services, "NEW-1")
    assert new_hire.get("/api/v1/mobile/auth/session").json()["bamboo_role"] == "INSPECTOR"


def test_system_admin_can_add_future_factory(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "ADMIN-1", "SYSTEM_ADMIN")
    admin = _client(services, "ADMIN-1")

    created = admin.post(
        "/api/v1/mobile/bamboo/admin/factories",
        headers=_headers(admin, "add-factory-b"),
        json={"code": "FACTORY-B", "name": "竹丝二厂"},
    )
    assert created.status_code == 201
    assert created.json()["code"] == "FACTORY-B"
