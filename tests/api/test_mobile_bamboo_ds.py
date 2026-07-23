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


def test_bamboo_independent_forms_open_by_role_and_validate_production_values(
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
                "shade": "深",
                "grade": "A",
                "bundle_count": 16,
            }
        },
    )
    assert created.status_code == 201
    sorting = created.json()
    record_id = sorting["record_id"]
    assert sorting["current_stage"] == "SORT"
    assert sorting["form_type"] == "SORTING"
    assert sorting["production_object_id"] == record_id
    assert sorting["source_record_id"] is None
    assert sorting["source_snapshot"] == {}
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
        json={
            "expected_revision": 1,
            "device_id": "sort-phone",
            "values": {"moisture": [12, 13, 14]},
        },
    )
    assert wrong_stage.status_code == 409
    assert wrong_stage.json()["code"] == "STAGE_NOT_AVAILABLE"
    stale = sort_client.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit",
        headers=_write_headers(sort_client, "stale-stage"),
        json={
            "expected_revision": 99,
            "device_id": "sort-phone",
            "values": {"moisture": [12, 13, 14]},
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_REVISION"

    signed = sort_client.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit",
        headers=_write_headers(sort_client, "sort-1"),
        json={
            "expected_revision": 1,
            "device_id": "sort-phone",
            "values": {"moisture": [12, 13, 14]},
        },
    )
    assert signed.status_code == 200
    assert signed.json()["current_stage"] == "SUPERVISOR"
    assert sort_client.get("/api/v1/mobile/bamboo/dashboard").json()["completed"] == 1

    replayed = sort_client.post(
        f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit",
        headers=_write_headers(sort_client, "sort-1"),
        json={
            "expected_revision": 1,
            "device_id": "sort-phone",
            "values": {"moisture": [99]},
        },
    )
    assert replayed.status_code == 200
    assert replayed.json()["record_id"] == record_id

    dipping_tasks = dipping_client.get("/api/v1/mobile/bamboo/tasks").json()["tasks"]
    assert len(dipping_tasks) == 1
    linked = dipping_tasks[0]
    linked_id = linked["record_id"]
    assert linked["form_type"] == "DIPPING_DRYING"
    assert linked["current_stage"] == "DIPPING"
    assert linked["source_record_id"] == record_id
    assert linked["production_object_id"] == sorting["production_object_id"]
    assert linked["source_snapshot"]["record_id"] == record_id
    assert dipping_client.get(f"/api/v1/mobile/bamboo/records/{record_id}").status_code == 404
    assert drying_client.get(
        f"/api/v1/mobile/bamboo/records/{linked_id}"
    ).status_code == 404
    assert drying_client.get("/api/v1/mobile/bamboo/dashboard").json()["waiting"] == 1

    invalid_weight = dipping_client.post(
        f"/api/v1/mobile/bamboo/records/{linked_id}/stages/DIPPING/submit",
        headers=_write_headers(dipping_client, "dip-invalid-weight"),
        json={
            "expected_revision": 1,
            "device_id": "dip-phone",
            "values": {
                "moisture": [11, 12, 13],
                "glue_before_weight": "10",
                "glue_after_weight": "9",
            },
        },
    )
    assert invalid_weight.status_code == 422
    assert invalid_weight.json()["code"] == "INVALID_BAMBOO_STAGE_VALUES"

    dipped = dipping_client.post(
        f"/api/v1/mobile/bamboo/records/{linked_id}/stages/DIPPING/submit",
        headers=_write_headers(dipping_client, "dip-without-weight"),
        json={
            "expected_revision": 1,
            "device_id": "dip-phone",
            "values": {"moisture": [11, 12, 13]},
        },
    )
    assert dipped.status_code == 200
    assert dipped.json()["current_stage"] == "DRYING"

    duplicate_racks = drying_client.post(
        f"/api/v1/mobile/bamboo/records/{linked_id}/stages/DRYING/submit",
        headers=_write_headers(drying_client, "dry-duplicate-racks"),
        json={
            "expected_revision": 2,
            "device_id": "dry-phone",
            "values": {
                "moisture": [8, 9, 10],
                "rack_numbers": ["R-01", "R-01"],
            },
        },
    )
    assert duplicate_racks.status_code == 422
    assert duplicate_racks.json()["code"] == "INVALID_BAMBOO_STAGE_VALUES"

    dried = drying_client.post(
        f"/api/v1/mobile/bamboo/records/{linked_id}/stages/DRYING/submit",
        headers=_write_headers(drying_client, "dry-valid-racks"),
        json={
            "expected_revision": 2,
            "device_id": "dry-phone",
            "values": {
                "moisture": [8, 9, 10],
                "rack_numbers": ["R-01", "R-02"],
                "rack_count": 999,
            },
        },
    )
    assert dried.status_code == 200
    assert dried.json()["current_stage"] == "SUPERVISOR"
    assert dried.json()["submissions"][-1]["values"]["rack_count"] == 2


def test_bamboo_mode_accepts_sorting_variants_and_rejects_caging_only(
    tmp_path: Path,
) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_bamboo_user(services, employee_code="E-SORT", role="SORT_OPERATOR")
    client = _client(services, "E-SORT")

    def create(mode: str, key: str) -> object:
        return client.post(
            "/api/v1/mobile/bamboo/records",
            headers=_write_headers(client, key),
            json={
                "base_info": {
                    "mode": mode,
                    "cage_no": key,
                    "length": "2.3",
                    "shade": "深",
                    "grade": "A",
                    "bundle_count": 10,
                }
            },
        )

    sorting = create("分选", "mode-sort")
    sorting_and_caging = create("分选+装笼", "mode-sort-cage")
    caging_only = create("装笼", "mode-cage")

    assert sorting.status_code == 201
    assert sorting.json()["base_info"]["mode"] == "分选"
    assert sorting_and_caging.status_code == 201
    assert sorting_and_caging.json()["base_info"]["mode"] == "分选+装笼"
    assert caging_only.status_code == 422
    assert caging_only.json()["code"] == "INVALID_BAMBOO_BASE_INFO"


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
        json={
            "base_info": {
                "cage_no": "A-001",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 10,
            }
        },
    )
    assert created.status_code == 201

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
    factory_b_record = factory_b.post(
        "/api/v1/mobile/bamboo/records",
        headers=_write_headers(factory_b, "create-b"),
        json={
            "base_info": {
                "cage_no": "B-001",
                "length": "2.1",
                "shade": "浅",
                "grade": "B",
                "bundle_count": 8,
            }
        },
    )
    assert factory_b_record.status_code == 201
    assert factory_b_record.json()["display_no"] != created.json()["display_no"]


def test_duplicate_active_cage_returns_stable_conflict(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_bamboo_user(services, employee_code="E-SORT", role="SORT_OPERATOR")
    client = _client(services, "E-SORT")
    base_info = {
        "cage_no": "CAGE-18",
        "length": "2.3",
        "shade": "深",
        "grade": "A",
        "bundle_count": 10,
    }
    first = client.post(
        "/api/v1/mobile/bamboo/records",
        headers=_write_headers(client, "cage-first"),
        json={"base_info": base_info},
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/v1/mobile/bamboo/records",
        headers=_write_headers(client, "cage-duplicate"),
        json={"base_info": {**base_info, "cage_no": " cage-18 "}},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "CAGE_ALREADY_IN_USE"
    assert duplicate.json()["cage_no"] == "CAGE-18"
    assert duplicate.json()["sorting_record_id"] == first.json()["record_id"]


def test_non_production_roles_read_scoped_records_and_linked_upstream_inline(
    tmp_path: Path,
) -> None:
    services = build_services(Settings(data_root=tmp_path))
    for code, role, factory_id in (
        ("E-SORT", "SORT_OPERATOR", "FACTORY-A"),
        ("E-DIP", "DIPPING_OPERATOR", "FACTORY-A"),
        ("E-INSPECT", "INSPECTOR", "FACTORY-A"),
        ("E-SUP", "SUPERVISOR", "FACTORY-A"),
        ("E-MANAGER", "PLANT_MANAGER", "FACTORY-A"),
        ("E-FINANCE", "FINANCE_APPROVER", "FACTORY-B"),
        ("E-ADMIN", "SYSTEM_ADMIN", "FACTORY-B"),
        ("E-MANAGER-B", "PLANT_MANAGER", "FACTORY-B"),
    ):
        _add_bamboo_user(
            services,
            employee_code=code,
            role=role,
            factory_id=factory_id,
        )
    clients = {
        code: _client(services, code)
        for code in (
            "E-SORT",
            "E-DIP",
            "E-INSPECT",
            "E-SUP",
            "E-MANAGER",
            "E-FINANCE",
            "E-ADMIN",
            "E-MANAGER-B",
        )
    }
    created = clients["E-SORT"].post(
        "/api/v1/mobile/bamboo/records",
        headers=_write_headers(clients["E-SORT"], "visibility-create"),
        json={
            "base_info": {
                "cage_no": "VISIBLE-1",
                "length": "2.3",
                "shade": "深",
                "grade": "A",
                "bundle_count": 10,
            }
        },
    ).json()
    record_url = f"/api/v1/mobile/bamboo/records/{created['record_id']}"

    for code in ("E-INSPECT", "E-SUP", "E-MANAGER", "E-FINANCE", "E-ADMIN"):
        assert clients[code].get(record_url).status_code == 200
    assert clients["E-DIP"].get(record_url).status_code == 404
    assert clients["E-MANAGER-B"].get(record_url).status_code == 404

    clients["E-SORT"].post(
        f"{record_url}/stages/SORT/submit",
        headers=_write_headers(clients["E-SORT"], "visibility-sort"),
        json={
            "expected_revision": 1,
            "device_id": "sort-phone",
            "values": {"moisture": [12]},
        },
    )
    linked = clients["E-DIP"].get("/api/v1/mobile/bamboo/tasks").json()["tasks"][0]

    assert linked["upstream_record"]["record_id"] == created["record_id"]
    assert linked["upstream_record"]["base_info"]["cage_no"] == "VISIBLE-1"
    assert [item["stage"] for item in linked["upstream_record"]["submissions"]] == [
        "SORT"
    ]


def test_bamboo_record_options_are_published_and_enforced(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    _add_bamboo_user(services, employee_code="E-SORT", role="SORT_OPERATOR")
    _add_bamboo_user(services, employee_code="E-MANAGER", role="PLANT_MANAGER")
    sort_client = _client(services, "E-SORT")
    manager = _client(services, "E-MANAGER")

    defaults = sort_client.get("/api/v1/mobile/bamboo/record-options")
    assert defaults.status_code == 200
    assert defaults.json()["lengths"] == ["2.1", "2.3", "2.5"]
    assert defaults.json()["shades"] == ["深", "浅"]
    assert defaults.json()["grades"] == ["A", "B"]

    invalid = sort_client.post(
        "/api/v1/mobile/bamboo/records",
        headers=_write_headers(sort_client, "invalid-length"),
        json={
            "base_info": {
                "cage_no": "3-099",
                "length": "9.9",
                "shade": "深",
                "grade": "A",
                "bundle_count": 16,
            }
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "INVALID_BAMBOO_BASE_INFO"

    rule = manager.post(
        "/api/v1/mobile/bamboo/payroll-rules",
        headers=_write_headers(manager, "publish-options"),
        json={
            "rule_key": "SORT",
            "configuration": {
                "unit_rate": "1.00",
                "length_multipliers": {"2.8": "9"},
                "special_classes": ["直装", "防霉", "加急"],
                "shades": ["深"],
                "grades": ["A+"],
                "weight_factors": {"2.8": "9"},
            },
            "system_default": False,
        },
    )
    assert rule.status_code == 201
    published = sort_client.get("/api/v1/mobile/bamboo/record-options").json()
    assert published["lengths"] == ["2.8"]
    assert published["special_classes"] == ["直装", "防霉", "加急"]
    assert published["grades"] == ["A+"]
