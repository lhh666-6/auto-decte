from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.adapters.database.models import BambooInspectionWindowRow
from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings


def _add_user(
    services: Services,
    code: str,
    role: str,
    factory_id: str = "FACTORY-A",
    factory_name: str = "竹丝一厂",
) -> None:
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
        factory_id=factory_id,
        factory_name=factory_name,
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


def test_inspection_queue_claims_once_and_accepts_one_click_conforming(
    tmp_path: Path,
) -> None:
    services = build_services(Settings(data_root=tmp_path, bamboo_plant_audit_wait_hours=0))
    for code, role in (
        ("SORT-Q", "SORT_OPERATOR"),
        ("INSPECT-Q1", "INSPECTOR"),
        ("INSPECT-Q2", "INSPECTOR"),
        ("SUP-Q", "SUPERVISOR"),
        ("MANAGER-Q", "PLANT_MANAGER"),
    ):
        _add_user(services, code, role)
    sort = _client(services, "SORT-Q")
    inspector = _client(services, "INSPECT-Q1")
    other_inspector = _client(services, "INSPECT-Q2")
    supervisor = _client(services, "SUP-Q")
    manager = _client(services, "MANAGER-Q")
    record = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers=_headers(sort, "queue-create"),
        json={
            "base_info": {
                "cage_no": "QUEUE-01",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 8,
            }
        },
    ).json()
    record_id = str(record["record_id"])
    _submit(sort, record_id, "SORT", 1, {"moisture": [12]})
    _submit(supervisor, record_id, "SUPERVISOR", 2, {"result": "APPROVED"})

    queue = inspector.get("/api/v1/mobile/bamboo/inspection-queue").json()
    assert [(item["record_id"], item["cage_no"]) for item in queue["items"]] == [
        (record_id, "QUEUE-01")
    ]
    assert inspector.get(
        "/api/v1/mobile/bamboo/inspection-queue", params={"q": "queue-01"}
    ).json()["items"][0]["record_id"] == record_id
    assert inspector.get(
        "/api/v1/mobile/bamboo/inspection-queue", params={"q": "不存在"}
    ).json()["items"] == []
    claimed = inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{record_id}/claim",
        headers=_headers(inspector, "queue-claim"),
    )
    assert claimed.status_code == 200
    assert claimed.json()["claimed_by"] == "INSPECT-Q1"
    rejected = other_inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{record_id}/claim",
        headers=_headers(other_inspector, "queue-other-claim"),
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "INSPECTION_ALREADY_CLAIMED"

    inspection = inspector.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/inspections",
        headers=_headers(inspector, "queue-result"),
        json={"conclusion": "CONFORMING", "device_id": "inspect-phone"},
    )
    assert inspection.status_code == 201, inspection.text
    assert inspection.json()["display_text"] == "检测合格"
    duplicate = inspector.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/inspections",
        headers=_headers(inspector, "queue-result-duplicate"),
        json={"conclusion": "CONFORMING", "device_id": "inspect-phone"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "INSPECTION_ALREADY_SUBMITTED"
    audited = _submit(manager, record_id, "PLANT_AUDIT", 3, {"result": "APPROVED"})
    assert audited["status"] == "COMPLETED"

    second = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers=_headers(sort, "queue-create-abnormal"),
        json={
            "base_info": {
                "cage_no": "QUEUE-02",
                "length": "2.3",
                "shade": "浅",
                "grade": "B",
                "bundle_count": 4,
            }
        },
    ).json()
    second_id = str(second["record_id"])
    _submit(sort, second_id, "SORT", 1, {"moisture": [11]})
    _submit(supervisor, second_id, "SUPERVISOR", 2, {"result": "APPROVED"})
    inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{second_id}/claim",
        headers=_headers(inspector, "queue-claim-abnormal"),
    ).raise_for_status()
    missing_evidence = inspector.post(
        f"/api/v1/mobile/bamboo/records/{second_id}/inspections",
        headers=_headers(inspector, "queue-result-no-evidence"),
        json={"conclusion": "NONCONFORMING", "device_id": "inspect-phone"},
    )
    assert missing_evidence.status_code == 409
    assert missing_evidence.json()["code"] == "INSPECTION_EVIDENCE_REQUIRED"
    abnormal = inspector.post(
        f"/api/v1/mobile/bamboo/records/{second_id}/inspection-submit",
        headers=_headers(inspector, "queue-result-abnormal"),
        data={
            "conclusion": "NONCONFORMING",
            "target_stage": "SORT",
            "device_id": "inspect-phone",
        },
        files={"photos": ("现场.jpg", b"photo-evidence", "image/jpeg")},
    )
    assert abnormal.status_code == 201
    assert abnormal.json()["exception"]["status"] == "OPEN"
    assert abnormal.json()["evidence"][0]["evidence_type"] == "PHOTO"
    history = inspector.get(
        "/api/v1/mobile/bamboo/inspection-queue", params={"bucket": "history"}
    ).json()["items"]
    assert {item["record_id"] for item in history} == {record_id, second_id}


def test_manager_termination_appeal_and_durable_notifications(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path, bamboo_plant_audit_wait_hours=0))
    for code, role in (
        ("SORT-A", "SORT_OPERATOR"),
        ("INSPECT-A1", "INSPECTOR"),
        ("INSPECT-A2", "INSPECTOR"),
        ("SUP-A", "SUPERVISOR"),
        ("MANAGER-A", "PLANT_MANAGER"),
    ):
        _add_user(services, code, role)
    sort = _client(services, "SORT-A")
    inspector = _client(services, "INSPECT-A1")
    other_inspector = _client(services, "INSPECT-A2")
    supervisor = _client(services, "SUP-A")
    manager = _client(services, "MANAGER-A")
    record = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers=_headers(sort, "appeal-create"),
        json={
            "base_info": {
                "cage_no": "APPEAL-01",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 5,
            }
        },
    ).json()
    record_id = str(record["record_id"])
    _submit(sort, record_id, "SORT", 1, {"moisture": [12]})
    _submit(supervisor, record_id, "SUPERVISOR", 2, {"result": "APPROVED"})
    inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{record_id}/claim",
        headers=_headers(inspector, "appeal-normal-claim"),
    ).raise_for_status()

    terminated = manager.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{record_id}/terminate",
        headers=_headers(manager, "appeal-terminate"),
        json={"confirm": True},
    )
    assert terminated.status_code == 200
    assert terminated.json()["status"] == "EARLY_TERMINATED"
    stopped = inspector.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/inspections",
        headers=_headers(inspector, "appeal-stopped-result"),
        json={"conclusion": "CONFORMING", "device_id": "phone"},
    )
    assert stopped.status_code == 409
    assert stopped.json()["code"] == "INSPECTION_CLAIM_REQUIRED"
    for client in (inspector, other_inspector):
        inbox = client.get("/api/v1/mobile/bamboo/notifications").json()["items"]
        assert inbox[0]["category"] == "INSPECTION_TERMINATED"
    _submit(manager, record_id, "PLANT_AUDIT", 3, {"result": "APPROVED"})

    appeal = inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{record_id}/appeal/claim",
        headers=_headers(inspector, "appeal-claim"),
    )
    assert appeal.status_code == 200
    reserved = other_inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{record_id}/appeal/claim",
        headers=_headers(other_inspector, "appeal-other-claim"),
    )
    assert reserved.status_code == 409
    assert reserved.json()["code"] == "APPEAL_RESERVED_FOR_ORIGINAL_INSPECTOR"
    submitted = inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{record_id}/appeal",
        headers=_headers(inspector, "appeal-submit"),
        json={"target_stage": "SORT", "text_evidence": "复核发现竹丝受潮"},
    )
    assert submitted.status_code == 200
    decision = manager.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{record_id}/appeal/decision",
        headers=_headers(manager, "appeal-decision"),
        json={"approve": False, "note": "复核批次正常"},
    )
    assert decision.status_code == 200
    assert decision.json()["appeal_decision"] == "REJECTED"
    assert inspector.get("/api/v1/mobile/bamboo/notifications").json()["items"][0][
        "category"
    ] == "APPEAL_DECIDED"

    expired_record = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers=_headers(sort, "appeal-expired-create"),
        json={
            "base_info": {
                "cage_no": "APPEAL-02",
                "length": "2.3",
                "shade": "浅",
                "grade": "B",
                "bundle_count": 2,
            }
        },
    ).json()
    expired_id = str(expired_record["record_id"])
    _submit(sort, expired_id, "SORT", 1, {"moisture": [10]})
    _submit(supervisor, expired_id, "SUPERVISOR", 2, {"result": "APPROVED"})
    manager.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{expired_id}/terminate",
        headers=_headers(manager, "appeal-expired-terminate"),
        json={"confirm": True},
    ).raise_for_status()
    with Session(services.engine) as session, session.begin():
        window = session.get(BambooInspectionWindowRow, expired_id)
        assert window is not None
        window.appeal_deadline_at = datetime.now(UTC) - timedelta(seconds=1)
    expired = other_inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{expired_id}/appeal/claim",
        headers=_headers(other_inspector, "appeal-expired-claim"),
    )
    assert expired.status_code == 409
    assert expired.json()["code"] == "APPEAL_WINDOW_EXPIRED"

    approved_record = sort.post(
        "/api/v1/mobile/bamboo/records",
        headers=_headers(sort, "appeal-approved-create"),
        json={
            "base_info": {
                "cage_no": "APPEAL-03",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 3,
            }
        },
    ).json()
    approved_id = str(approved_record["record_id"])
    _submit(sort, approved_id, "SORT", 1, {"moisture": [9]})
    _submit(supervisor, approved_id, "SUPERVISOR", 2, {"result": "APPROVED"})
    manager.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{approved_id}/terminate",
        headers=_headers(manager, "appeal-approved-terminate"),
        json={"confirm": True},
    ).raise_for_status()
    other_inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{approved_id}/appeal/claim",
        headers=_headers(other_inspector, "appeal-approved-claim"),
    ).raise_for_status()
    other_inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{approved_id}/appeal",
        headers=_headers(other_inspector, "appeal-approved-submit"),
        json={"target_stage": "SORT", "text_evidence": "复测确认分选异常"},
    ).raise_for_status()
    approved = manager.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{approved_id}/appeal/decision",
        headers=_headers(manager, "appeal-approved-decision"),
        json={"approve": True, "note": "同意回溯"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["return"]["current_stage"] == "SORT"


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

    inspector_tasks = inspector.get(
        "/api/v1/mobile/bamboo/tasks",
        params={"bucket": "available", "cage_no": "L-207"},
    ).json()["tasks"]
    assert {item["record_id"] for item in inspector_tasks} == {sorting_id, linked_id}
    assert inspector.get(
        "/api/v1/mobile/bamboo/tasks",
        params={"bucket": "available", "cage_no": "不存在"},
    ).json()["tasks"] == []

    _submit(supervisor, linked_id, "SUPERVISOR", 3, {"result": "APPROVED"})
    inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{linked_id}/claim",
        headers=_headers(inspector, "inspect-claim-1"),
    ).raise_for_status()
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
    inspector_history = inspector.get("/api/v1/mobile/bamboo/history").json()
    assert inspector_history[0]["action"] == "INSPECTION"
    assert inspector_history[0]["cage_no"] == "L-207"

    blocked = manager.post(
        f"/api/v1/mobile/bamboo/records/{linked_id}/stages/PLANT_AUDIT/submit",
        headers=_headers(manager, "manager-blocked"),
        json={"expected_revision": 4, "device_id": "phone", "values": {}},
    )
    assert blocked.status_code == 409
    inspector.post(
        f"/api/v1/mobile/bamboo/inspection-exceptions/{exception_id}/close",
        headers=_headers(inspector, "close-exception"),
        json={"resolution": "复测合格"},
    ).raise_for_status()

    linked_audit = _submit(
        manager,
        linked_id,
        "PLANT_AUDIT",
        4,
        {"result": "APPROVED"},
    )
    _submit(supervisor, sorting_id, "SUPERVISOR", 2, {"result": "APPROVED"})
    inspector.post(
        f"/api/v1/mobile/bamboo/inspection-queue/{sorting_id}/claim",
        headers=_headers(inspector, "inspect-claim-sort"),
    ).raise_for_status()
    inspector.post(
        f"/api/v1/mobile/bamboo/records/{sorting_id}/inspections",
        headers=_headers(inspector, "inspect-sort"),
        json={"conclusion": "CONFORMING", "device_id": "inspect-phone"},
    ).raise_for_status()
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


def test_personnel_transfers_require_managers_and_admin_execution(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "SORT-1", "SORT_OPERATOR")
    _add_user(services, "MANAGER-A", "PLANT_MANAGER")
    _add_user(services, "MANAGER-B", "PLANT_MANAGER", "FACTORY-B", "竹丝二厂")
    _add_user(services, "ADMIN-1", "SYSTEM_ADMIN")
    _add_user(services, "FUTURE-MANAGER", "SUPERVISOR", "FACTORY-B", "竹丝二厂")
    worker = _client(services, "SORT-1")
    manager_a = _client(services, "MANAGER-A")
    manager_b = _client(services, "MANAGER-B")
    admin = _client(services, "ADMIN-1")

    requested = worker.post(
        "/api/v1/mobile/bamboo/role-change-requests",
        headers=_headers(worker, "role-change"),
        json={"to_role": "DIPPING_OPERATOR", "reason": "转岗培训已完成"},
    )
    assert requested.status_code == 409
    assert requested.json()["code"] == "WORKER_TRANSFER_FORBIDDEN"

    internal = manager_a.post(
        "/api/v1/mobile/bamboo/personnel-transfers",
        headers=_headers(manager_a, "internal-transfer"),
        json={
            "employee_code": "SORT-1",
            "to_role": "DIPPING_OPERATOR",
            "target_factory_id": "FACTORY-A",
            "reason": "线下沟通后调整岗位",
        },
    )
    assert internal.status_code == 201
    assert internal.json()["status"] == "ADMIN_PENDING"
    internal_id = internal.json()["transfer_id"]
    admin.post(
        f"/api/v1/mobile/bamboo/personnel-transfers/{internal_id}/execute",
        headers=_headers(admin, "internal-execute"),
        json={"approve": True, "note": "管理员执行"},
    ).raise_for_status()

    refreshed = _client(services, "SORT-1")
    assert refreshed.get("/api/v1/mobile/auth/session").json()["bamboo_role"] == "DIPPING_OPERATOR"
    assert refreshed.get("/api/v1/mobile/bamboo/notifications").json()["items"][0][
        "category"
    ] == "PERSONNEL_TRANSFER_COMPLETED"

    cross = manager_a.post(
        "/api/v1/mobile/bamboo/personnel-transfers",
        headers=_headers(manager_a, "cross-transfer"),
        json={
            "employee_code": "SORT-1",
            "to_role": "SORT_OPERATOR",
            "target_factory_id": "FACTORY-B",
            "reason": "跨厂补充人员",
        },
    )
    assert cross.status_code == 201
    assert cross.json()["status"] == "TARGET_MANAGER_PENDING"
    cross_id = cross.json()["transfer_id"]
    bypass = admin.post(
        f"/api/v1/mobile/bamboo/personnel-transfers/{cross_id}/execute",
        headers=_headers(admin, "cross-bypass"),
        json={"approve": True, "note": "尝试跳过"},
    )
    assert bypass.status_code == 409
    assert bypass.json()["code"] == "BOTH_MANAGERS_REQUIRED"
    manager_b.post(
        f"/api/v1/mobile/bamboo/personnel-transfers/{cross_id}/manager-decision",
        headers=_headers(manager_b, "target-manager-approve"),
        json={"approve": True, "note": "二厂厂长同意"},
    ).raise_for_status()
    admin.post(
        f"/api/v1/mobile/bamboo/personnel-transfers/{cross_id}/execute",
        headers=_headers(admin, "cross-execute"),
        json={"approve": True, "note": "管理员执行跨厂调动"},
    ).raise_for_status()
    transferred = _client(services, "SORT-1").get("/api/v1/mobile/auth/session").json()
    assert transferred["factory_id"] == "FACTORY-B"
    assert transferred["bamboo_role"] == "SORT_OPERATOR"

    replacement = admin.post(
        "/api/v1/mobile/bamboo/personnel-transfers",
        headers=_headers(admin, "replace-manager"),
        json={
            "employee_code": "FUTURE-MANAGER",
            "to_role": "PLANT_MANAGER",
            "target_factory_id": "FACTORY-B",
            "reason": "管理员更换二厂厂长",
        },
    )
    assert replacement.status_code == 201
    admin.post(
        f"/api/v1/mobile/bamboo/personnel-transfers/{replacement.json()['transfer_id']}/execute",
        headers=_headers(admin, "replace-manager-execute"),
        json={"approve": True, "note": "执行厂长更换"},
    ).raise_for_status()
    new_manager = _client(services, "FUTURE-MANAGER")
    assert new_manager.get("/api/v1/mobile/auth/session").json()["bamboo_role"] == "PLANT_MANAGER"


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


def test_manager_adds_people_only_with_published_business_roles(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_user(services, "MANAGER-1", "PLANT_MANAGER")
    manager = _client(services, "MANAGER-1")

    role_options = manager.get("/api/v1/mobile/bamboo/role-options").json()
    assert {item["display_name"] for item in role_options} >= {
        "分选工", "浸胶工", "干燥工", "检测人", "主管"
    }
    assert "PLANT_MANAGER" not in {item["role_code"] for item in role_options}

    created = manager.post(
        "/api/v1/mobile/bamboo/admin/employees",
        headers=_headers(manager, "create-person"),
        json={"employee_name": "新检测员", "initial_pin": "1357", "role_code": "INSPECTOR"},
    )
    assert created.status_code == 201
    assert created.json() == {
        "employee_code": "YG0001",
        "employee_name": "新检测员",
        "role_code": "INSPECTOR",
        "role_name": "检测人",
    }
    people = manager.get("/api/v1/mobile/bamboo/admin/employees").json()
    assert any(item["employee_code"] == "YG0001" for item in people)
    new_person = TestClient(create_app(services))
    login = new_person.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "YG0001", "pin": "1357", "device_id": "new-phone"},
    )
    assert login.status_code == 200
    assert new_person.get("/api/v1/mobile/auth/session").json()["bamboo_role"] == "INSPECTOR"

    rejected = manager.post(
        "/api/v1/mobile/bamboo/admin/assignments",
        headers=_headers(manager, "unknown-role"),
        json={"employee_code": "YG0001", "role_code": "NEW_UNPUBLISHED_ROLE"},
    )
    assert rejected.status_code == 409
    assert "ASSIGNMENT_FORBIDDEN" in rejected.text


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
