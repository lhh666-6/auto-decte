from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import Form, FormField, ReviewStatus
from app.domain.templates_ds import FieldDefinition, FieldRules, PageSpec, Rect, TemplateVersion
from app.services.container import Services, build_services
from config.settings import Settings


def _headers(role: str = "ADMIN", actor: str = "admin-a") -> dict[str, str]:
    return {"X-Actor-ID": actor, "X-Roles": role}


def _client(tmp_path: Path) -> tuple[TestClient, Services]:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    return TestClient(create_app(services), raise_server_exceptions=False), services


def _create(
    client: TestClient,
    catalog: str,
    code: str,
    name: str,
    *,
    attributes: dict[str, object] | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/master-data/{catalog}",
        headers=_headers(),
        json={
            "code": code,
            "display_name": name,
            "attributes": attributes or {},
            "reason": "初始化主数据",
        },
    )
    assert response.status_code == 201, response.text
    assert response.headers["etag"] == '"1"'
    return response.json()


@pytest.mark.parametrize(
    ("catalog", "code", "name", "attributes"),
    [
        ("employees", "E001", "张三", {"team": "A班", "role": "操作员"}),
        (
            "work-orders",
            "WO-001",
            "七月标准件订单",
            {"product_code": "P001", "planned_quantity": 100},
        ),
        ("products", "P001", "标准板", {"specification": "100x200", "unit": "张"}),
        (
            "processes",
            "PROC-01",
            "热压",
            {"product_code": "P001", "sequence": 10, "station": "热压一线"},
        ),
    ],
)
def test_admin_can_create_and_read_each_master_data_catalog(
    tmp_path: Path,
    catalog: str,
    code: str,
    name: str,
    attributes: dict[str, object],
) -> None:
    client, _ = _client(tmp_path)

    created = _create(client, catalog, code, name, attributes=attributes)
    detail = client.get(f"/api/v1/master-data/{catalog}/{code}", headers=_headers())
    listed = client.get(f"/api/v1/master-data/{catalog}", headers=_headers("OPERATOR"))

    assert created["catalog"] == catalog
    assert created["code"] == code
    assert created["revision"] == 1
    assert created["active"] is True
    assert detail.status_code == 200
    assert detail.headers["etag"] == '"1"'
    assert detail.json()["attributes"] == attributes
    assert [item["code"] for item in listed.json()["items"]] == [code]


def test_update_uses_optimistic_revision_and_code_is_immutable(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    _create(client, "employees", "E001", "张三")

    updated = client.patch(
        "/api/v1/master-data/employees/E001",
        headers={**_headers(), "If-Match": '"1"'},
        json={
            "expected_revision": 99,
            "display_name": "张三（装配）",
            "attributes": {"team": "装配班"},
            "reason": "调岗",
        },
    )
    stale = client.patch(
        "/api/v1/master-data/employees/E001",
        headers=_headers(),
        json={
            "expected_revision": 1,
            "display_name": "旧页面覆盖",
            "reason": "错误重试",
        },
    )
    attempted_rename = client.patch(
        "/api/v1/master-data/employees/E001",
        headers=_headers(),
        json={
            "expected_revision": 2,
            "code": "E999",
            "reason": "禁止改编码",
        },
    )

    assert updated.status_code == 200
    assert updated.headers["etag"] == '"2"'
    assert updated.json()["display_name"] == "张三（装配）"
    assert stale.status_code == 409
    assert stale.json()["code"] == "MASTER_DATA_REVISION_CONFLICT"
    assert stale.json()["submitted_revision"] == 1
    assert stale.json()["current_revision"] == 2
    assert attempted_rename.status_code == 422


def test_deactivate_and_reactivate_are_audited_without_physical_delete(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    _create(client, "products", "P001", "标准板")

    deactivated = client.post(
        "/api/v1/master-data/products/P001/deactivate",
        headers=_headers(),
        json={"expected_revision": 1, "reason": "产品停产"},
    )
    active_list = client.get("/api/v1/master-data/products", headers=_headers())
    all_list = client.get(
        "/api/v1/master-data/products?include_inactive=true", headers=_headers()
    )
    reactivated = client.post(
        "/api/v1/master-data/products/P001/reactivate",
        headers=_headers(),
        json={"expected_revision": 2, "reason": "恢复生产"},
    )
    audit = client.get(
        "/api/v1/master-data/products/P001/audit", headers=_headers("AUDITOR")
    )
    deleted = client.delete("/api/v1/master-data/products/P001", headers=_headers())

    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False
    assert active_list.json()["items"] == []
    assert all_list.json()["items"][0]["active"] is False
    assert reactivated.status_code == 200
    assert reactivated.json()["active"] is True
    assert [event["event_type"] for event in audit.json()] == [
        "CREATE",
        "DEACTIVATE",
        "REACTIVATE",
    ]
    assert audit.json()[-1]["reason"] == "恢复生产"
    assert deleted.status_code == 405


def test_master_data_permissions_and_duplicate_conflict(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    _create(client, "processes", "PROC-01", "热压")

    duplicate = client.post(
        "/api/v1/master-data/processes",
        headers=_headers(),
        json={
            "code": "PROC-01",
            "display_name": "重复热压",
            "attributes": {},
            "reason": "重复创建",
        },
    )
    readable = client.get(
        "/api/v1/master-data/processes", headers=_headers("REVIEWER", "reviewer-a")
    )
    forbidden = client.post(
        "/api/v1/master-data/processes",
        headers=_headers("OPERATOR", "operator-a"),
        json={
            "code": "PROC-02",
            "display_name": "包装",
            "attributes": {},
            "reason": "无权创建",
        },
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "MASTER_DATA_ALREADY_EXISTS"
    assert readable.status_code == 200
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "PERMISSION_DENIED"


def test_review_uses_active_master_data_options_and_blocks_unknown_codes(
    tmp_path: Path,
) -> None:
    client, services = _client(tmp_path)
    _create(client, "employees", "E001", "张三", attributes={"team": "A班"})
    _create(client, "employees", "E002", "李四")
    client.post(
        "/api/v1/master-data/employees/E002/deactivate",
        headers=_headers(),
        json={"expected_revision": 1, "reason": "离职"},
    )
    page = PageSpec.a4_portrait()
    template = TemplateVersion.draft("TPL-MASTER-V1", "MASTER_REVIEW", 1, page)
    template.add_field(
        FieldDefinition(
            field_key="employee_id",
            display_name="员工",
            data_type="text",
            input_type="select",
            page=page,
            region=Rect(0.2, 0.2, 0.2, 0.05),
            rules=FieldRules(required=True, master_data_source="employees"),
        )
    )
    template.mark_ready_to_publish()
    template.publish()
    services.template_repository.add_version(template)
    services.repository.add_form(
        Form(
            "FORM-MASTER",
            "MASTER_REVIEW",
            "1",
            review_status=ReviewStatus.NEEDS_REVIEW,
            created_at=datetime(2026, 7, 15, tzinfo=UTC),
        )
    )
    services.repository.add_form_field(
        FormField(
            "FORM-MASTER:employee_id",
            "FORM-MASTER",
            "employee_id",
            {"x": 10, "y": 10, "width": 80, "height": 20},
        )
    )
    reviewer = _headers("REVIEWER", "reviewer-a")

    detail = client.get("/api/v1/forms/FORM-MASTER", headers=reviewer)
    lease = client.post("/api/v1/forms/FORM-MASTER/review-lease", headers=reviewer).json()
    blocked = client.post(
        "/api/v1/forms/FORM-MASTER/confirm-and-claim-next",
        headers=reviewer,
        json={
            "expected_version": 0,
            "lease_token": lease["lease_token"],
            "values": {"FORM-MASTER:employee_id": "E999"},
            "reason": "人工复核",
            "evidence_ids": [],
            "queue_key": "review",
        },
    )
    confirmed = client.post(
        "/api/v1/forms/FORM-MASTER/confirm-and-claim-next",
        headers=reviewer,
        json={
            "expected_version": 0,
            "lease_token": lease["lease_token"],
            "values": {"FORM-MASTER:employee_id": "E001"},
            "reason": "人工复核",
            "evidence_ids": [],
            "queue_key": "review",
        },
    )

    rules = detail.json()["fields"][0]["rules"]
    assert rules["master_data_source"] == "employees"
    assert rules["master_data_options"] == [{"value": "E001", "label": "张三"}]
    assert blocked.status_code == 422
    assert blocked.json()["failures"] == [
        {
            "code": "INVALID_WORKER_NUMBER",
            "field_key": "employee_id",
            "message": "工号未在员工库中匹配，必须人工处理",
        }
    ]
    assert confirmed.status_code == 200
