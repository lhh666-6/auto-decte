"""Template management API behavior."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.templates_ds import ElementKind, Rect, StaticElement
from app.services.container import build_services
from config.settings import Settings


def _headers() -> dict[str, str]:
    return {"X-Actor-ID": "admin-a", "X-Roles": "ADMIN"}


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(build_services(Settings(data_root=tmp_path, allow_header_identity=True))),
        raise_server_exceptions=False,
    )


def _field(display_name: str = "Worker name") -> dict[str, object]:
    return {
        "field_key": "worker_name",
        "display_name": display_name,
        "data_type": "text",
        "input_type": "text_box",
        "recognition_engine": "manual",
        "minimum_prefill_confidence": 1.0,
        "paper_entry_mode": "HANDWRITTEN_TEXT",
        "recognition_mode": "NONE",
        "fill_policy": "MANUAL_ONLY",
        "confidence_threshold": None,
        "requires_manual_confirmation": True,
        "calculation_expression": None,
        "digit_count": None,
        "choice_group": None,
        "choice_options": [],
        "max_selections": None,
        "derived_from_field_key": None,
        "conditional_required_on": None,
        "signature_role": None,
        "rules": {
            "required": False,
            "minimum_value": None,
            "maximum_value": None,
            "allowed_values": [],
            "master_data_source": None,
            "allow_exception_reason": False,
        },
        "export_target": {
            "workbook": "records.xlsx",
            "worksheet": "records",
            "business_column": "worker_name",
        },
        "region": {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.05},
    }


def _table_grid(rows: int = 3, columns: int = 4) -> dict[str, object]:
    return {
        "element_id": "detail_grid",
        "kind": "TABLE_GRID",
        "text": "",
        "rows": rows,
        "columns": columns,
        "column_weights": [2, 1, 1, 1][:columns],
        "region": {"x": 0.1, "y": 0.3, "width": 0.8, "height": 0.4},
    }


def test_admin_can_replace_controlled_table_grid_configuration(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    client = TestClient(create_app(services), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_GRID", "page_size": "A4"},
    )
    version_id = created.json()["version_id"]

    services.templates.add_static_element(
        version_id,
        StaticElement(
            element_id="detail_grid",
            kind=ElementKind.TABLE_GRID,
            region=Rect(x=0.1, y=0.3, width=0.8, height=0.4),
            rows=2,
            columns=2,
            column_weights=(1, 1),
        ),
    )

    detail = client.get(
        f"/api/v1/template-versions/{version_id}", headers=_headers()
    )
    replaced = client.patch(
        f"/api/v1/template-versions/{version_id}/static-elements/detail_grid",
        headers=_headers(),
        json=_table_grid(),
    )
    invalid = client.patch(
        f"/api/v1/template-versions/{version_id}/static-elements/detail_grid",
        headers=_headers(),
        json=_table_grid(rows=0),
    )
    client.post(f"/api/v1/template-versions/{version_id}/preflight", headers=_headers())
    published = client.post(
        f"/api/v1/template-versions/{version_id}/publish", headers=_headers()
    )
    immutable = client.patch(
        f"/api/v1/template-versions/{version_id}/static-elements/detail_grid",
        headers=_headers(),
        json=_table_grid(rows=4),
    )

    assert detail.json()["static_elements"][0] == {
        **_table_grid(rows=2, columns=2),
        "column_weights": [1, 1],
    }
    assert replaced.status_code == 200
    assert replaced.json()["static_elements"] == [_table_grid()]
    assert invalid.status_code == 422
    assert replaced.json()["status"] == "DRAFT"
    assert published.status_code == 200
    assert immutable.status_code == 409


def _published_template(client: TestClient) -> str:
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"},
    )
    version_id = created.json()["version_id"]
    client.post(f"/api/v1/template-versions/{version_id}/fields", headers=_headers(), json=_field())
    client.post(f"/api/v1/template-versions/{version_id}/preflight", headers=_headers())
    client.post(f"/api/v1/template-versions/{version_id}/publish", headers=_headers())
    return version_id


def test_admin_creates_preflights_publishes_and_downloads_template_artifact(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"},
    )

    assert created.status_code == 201
    version_id = created.json()["version_id"]
    added = client.post(
        f"/api/v1/template-versions/{version_id}/fields", headers=_headers(), json=_field()
    )
    preflight = client.post(f"/api/v1/template-versions/{version_id}/preflight", headers=_headers())
    published = client.post(f"/api/v1/template-versions/{version_id}/publish", headers=_headers())

    assert added.status_code == 200
    assert added.json()["fields"] == [_field()]
    assert preflight.json()["ok"] is True
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"
    assert published.json()["static_elements"] == []
    assert published.json()["print_imposition"] is None
    artifact = published.json()["artifacts"][0]
    download = client.get(artifact["download_url"], headers=_headers())
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("image/")
    assert "internal_uri" not in repr(published.json())


def test_publish_is_blocked_before_state_change_when_chinese_font_is_missing(
    tmp_path: Path,
) -> None:
    services = build_services(
        Settings(
            data_root=tmp_path,
            allow_header_identity=True,
            cjk_font_path=tmp_path / "missing-cjk-font.ttf",
        )
    )
    client = TestClient(create_app(services), raise_server_exceptions=False)
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_FONT_CHECK", "page_size": "A4"},
    )
    version_id = created.json()["version_id"]
    client.post(
        f"/api/v1/template-versions/{version_id}/fields",
        headers=_headers(),
        json=_field("员工姓名"),
    )
    preflight = client.post(
        f"/api/v1/template-versions/{version_id}/preflight",
        headers=_headers(),
    )

    published = client.post(
        f"/api/v1/template-versions/{version_id}/publish",
        headers=_headers(),
    )
    detail = client.get(
        f"/api/v1/template-versions/{version_id}",
        headers=_headers(),
    )

    assert preflight.json()["ok"] is True
    assert published.status_code == 409
    assert published.json()["code"] == "CHINESE_FONT_UNAVAILABLE"
    assert detail.json()["status"] == "READY_TO_PUBLISH"
    assert detail.json()["artifacts"] == []


def test_admin_can_list_read_clone_patch_and_delete_template_draft(tmp_path: Path) -> None:
    client = _client(tmp_path)
    version_id = _published_template(client)

    library = client.get("/api/v1/templates", headers=_headers())
    detail = client.get(f"/api/v1/template-versions/{version_id}", headers=_headers())
    clone = client.post(f"/api/v1/template-versions/{version_id}/clone", headers=_headers())
    clone_id = clone.json()["version_id"]
    clone_detail = client.get(f"/api/v1/template-versions/{clone_id}", headers=_headers())
    patched_field = _field("Employee name")
    patched_field["region"] = {"x": 0.15, "y": 0.2, "width": 0.2, "height": 0.05}
    patched = client.patch(
        f"/api/v1/template-versions/{clone_id}/fields/worker_name",
        headers=_headers(),
        json=patched_field,
    )
    deleted = client.delete(
        f"/api/v1/template-versions/{clone_id}/fields/worker_name", headers=_headers()
    )

    assert library.status_code == 200
    assert library.json()[0]["template_key"] == "PAYROLL_HOURLY"
    assert library.json()[0]["version_id"] == version_id
    assert library.json()[0]["current_published_version"] == 1
    assert library.json()[0]["status"] == "PUBLISHED"
    assert library.json()[0]["page"]["size"] == "A4"
    assert library.json()[0]["field_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["parent_version_id"] is None
    assert detail.json()["page"]["size"] == "A4"
    assert detail.json()["page"]["orientation"] == "portrait"
    assert detail.json()["static_elements"] == []
    assert detail.json()["print_imposition"] is None
    assert detail.json()["fields"] == [_field()]
    assert detail.json()["artifacts"]
    assert "internal_uri" not in repr(detail.json())
    assert clone.status_code == 201
    assert clone.json()["status"] == "DRAFT"
    assert clone.json()["parent_version_id"] == version_id
    assert clone_detail.status_code == 200
    assert clone_detail.json()["artifacts"] == []
    assert {artifact["artifact_id"] for artifact in clone_detail.json()["artifacts"]}.isdisjoint(
        {artifact["artifact_id"] for artifact in detail.json()["artifacts"]}
    )
    assert patched.status_code == 200
    assert patched.json()["fields"] == [patched_field]
    assert deleted.status_code == 200
    assert deleted.json()["fields"] == []


def test_template_library_exposes_latest_editable_draft_alongside_published_version(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    published_id = _published_template(client)
    clone = client.post(f"/api/v1/template-versions/{published_id}/clone", headers=_headers())

    library = client.get("/api/v1/templates", headers=_headers())

    assert clone.status_code == 201
    assert library.status_code == 200
    assert library.json()[0]["version_id"] == published_id
    assert library.json()[0]["active_draft"] == {
        "version_id": clone.json()["version_id"],
        "version": 2,
        "status": "DRAFT",
        "field_count": 1,
    }


def test_admin_renames_discards_and_retires_templates_without_deleting_history(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    published_id = _published_template(client)

    renamed = client.patch(
        "/api/v1/templates/PAYROLL_HOURLY",
        headers=_headers(),
        json={"display_name": "新版计时工资单", "description": "车间计时记录"},
    )
    clone = client.post(
        f"/api/v1/template-versions/{published_id}/clone", headers=_headers()
    )
    blocked_retire = client.post(
        "/api/v1/templates/PAYROLL_HOURLY/retire", headers=_headers()
    )
    blocked_delete = client.delete(
        f"/api/v1/template-versions/{published_id}", headers=_headers()
    )
    discarded = client.delete(
        f"/api/v1/template-versions/{clone.json()['version_id']}", headers=_headers()
    )
    retired = client.post(
        "/api/v1/templates/PAYROLL_HOURLY/retire", headers=_headers()
    )
    library = client.get("/api/v1/templates", headers=_headers())
    historical = client.get(
        f"/api/v1/template-versions/{published_id}", headers=_headers()
    )

    assert renamed.status_code == 200
    assert renamed.json() == {
        "template_key": "PAYROLL_HOURLY",
        "display_name": "新版计时工资单",
        "description": "车间计时记录",
    }
    assert blocked_retire.status_code == 409
    assert blocked_delete.status_code == 409
    assert discarded.status_code == 204
    assert retired.status_code == 204
    assert library.json()[0]["display_name"] == "新版计时工资单"
    assert library.json()[0]["description"] == "车间计时记录"
    assert library.json()[0]["status"] == "RETIRED"
    assert library.json()[0]["active_draft"] is None
    assert historical.status_code == 200
    assert historical.json()["status"] == "RETIRED"
    assert historical.json()["artifacts"]


def test_template_library_api_maps_lifecycle_missing_and_permission_errors(tmp_path: Path) -> None:
    client = _client(tmp_path)
    version_id = _published_template(client)

    immutable = client.patch(
        f"/api/v1/template-versions/{version_id}/fields/worker_name",
        headers=_headers(),
        json=_field("Employee name"),
    )
    missing = client.get("/api/v1/template-versions/TPL-MISSING", headers=_headers())
    forbidden = client.get(
        "/api/v1/templates", headers={"X-Actor-ID": "operator-a", "X-Roles": "OPERATOR"}
    )

    assert immutable.status_code == 409
    assert immutable.json()["code"] == "INVALID_LIFECYCLE"
    assert missing.status_code == 404
    assert missing.json()["code"] == "TEMPLATE_VERSION_NOT_FOUND"
    assert forbidden.status_code == 403


def test_template_field_payload_validation_uses_invalid_field_problem_code(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"},
    )
    invalid_field = _field()
    invalid_field["minimum_prefill_confidence"] = -0.1

    response = client.post(
        f"/api/v1/template-versions/{created.json()['version_id']}/fields",
        headers=_headers(),
        json=invalid_field,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_FIELD"


def test_api_creates_custom_millimetre_page_and_returns_typed_field_behavior(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={
            "template_key": "PAYROLL_CUSTOM",
            "page": {
                "size": "CUSTOM",
                "orientation": "landscape",
                "width_mm": 123.4,
                "height_mm": 87.6,
                "canonical_dpi": 300,
            },
        },
    )
    field = {
        **_field("工号"),
        "field_key": "worker_number",
        "data_type": "integer",
        "input_type": "digit_boxes",
        "recognition_engine": "digit_template",
        "minimum_prefill_confidence": 0.97,
        "paper_entry_mode": "DIGIT_BOXES",
        "recognition_mode": "DIGIT_OCR",
        "fill_policy": "PREFILL_WHEN_CONFIDENT",
        "confidence_threshold": 0.97,
        "requires_manual_confirmation": False,
        "digit_count": 6,
        "export_target": {
            "workbook": "records.xlsx",
            "worksheet": "records",
            "business_column": "worker_number",
        },
    }
    added = client.post(
        f"/api/v1/template-versions/{created.json()['version_id']}/fields",
        headers=_headers(),
        json=field,
    )

    assert created.status_code == 201
    assert created.json()["page"] == {
        "size": "CUSTOM",
        "orientation": "landscape",
        "width_mm": 123.4,
        "height_mm": 87.6,
        "canonical_dpi": 300,
        "canonical_width_px": 1457,
        "canonical_height_px": 1035,
    }
    assert added.status_code == 200
    assert added.json()["fields"] == [field]


def test_custom_page_validation_returns_a_business_problem(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/api/v1/templates",
        headers=_headers(),
        json={
            "template_key": "PAYROLL_TOO_SMALL",
            "page": {
                "size": "CUSTOM",
                "orientation": "portrait",
                "width_mm": 70,
                "height_mm": 50,
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PAGE_SIZE"


def test_template_field_routes_declare_openapi_request_bodies(tmp_path: Path) -> None:
    schema = _client(tmp_path).app.openapi()

    fields_path = "/api/v1/template-versions/{version_id}/fields"
    field_path = "/api/v1/template-versions/{version_id}/fields/{field_key}"
    assert "requestBody" in schema["paths"][fields_path]["post"]
    assert "requestBody" in schema["paths"][field_path]["patch"]


def test_admin_manages_versioned_job_profiles_through_the_template_api(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    template = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "CORE_TIMEKEEPING", "page_size": "A5"},
    ).json()
    created = client.post(
        "/api/v1/job-profile-versions",
        headers=_headers(),
        json={
            "profile_key": "TIMEKEEPING_DAY",
            "version": 1,
            "display_name": "计时工白班",
            "core_layout": "TIMEKEEPING",
            "template_version_id": template["version_id"],
            "template_version": template["version"],
            "unit": "小时",
            "fixed_options": {"shift": ["白班"]},
            "pricing_rules": {"hourly_rate": 18.5},
            "deduction_rules": {},
            "export_mapping": {"normal_hours": "正常工时"},
        },
    )
    profile_id = created.json()["profile_version_id"]
    patched = client.patch(
        f"/api/v1/job-profile-versions/{profile_id}",
        headers=_headers(),
        json={"unit": "工时"},
    )
    listed = client.get(
        "/api/v1/job-profile-versions",
        headers=_headers(),
        params={"profile_key": "TIMEKEEPING_DAY"},
    )
    detail = client.get(
        f"/api/v1/job-profile-versions/{profile_id}", headers=_headers()
    )
    published = client.post(
        f"/api/v1/job-profile-versions/{profile_id}/publish", headers=_headers()
    )
    cloned = client.post(
        f"/api/v1/job-profile-versions/{profile_id}/clone",
        headers=_headers(),
        json={"version": 2},
    )
    retired = client.post(
        f"/api/v1/job-profile-versions/{profile_id}/retire", headers=_headers()
    )

    assert created.status_code == 201
    assert created.json()["profile_version_id"].startswith("PROFILE-")
    assert created.json()["core_layout"] == "TIMEKEEPING"
    assert created.json()["template_version_id"] == template["version_id"]
    assert patched.json()["unit"] == "工时"
    assert listed.json() == [patched.json()]
    assert detail.json() == patched.json()
    assert published.json()["status"] == "PUBLISHED"
    assert cloned.status_code == 201
    assert cloned.json()["status"] == "DRAFT"
    assert cloned.json()["parent_profile_version_id"] == profile_id
    assert retired.json()["status"] == "RETIRED"
    assert "internal" not in repr(created.json()).lower()


def test_job_profile_api_maps_missing_binding_and_permission_errors(tmp_path: Path) -> None:
    client = _client(tmp_path)
    missing = client.get(
        "/api/v1/job-profile-versions/PROFILE-MISSING", headers=_headers()
    )
    forbidden = client.post(
        "/api/v1/job-profile-versions",
        headers={"X-Actor-ID": "operator-a", "X-Roles": "OPERATOR"},
        json={
            "profile_key": "TIMEKEEPING_DAY",
            "version": 1,
            "display_name": "计时工",
            "core_layout": "TIMEKEEPING",
            "template_version_id": "TPL-ANY",
            "template_version": 1,
        },
    )
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "CORE_TIMEKEEPING", "page_size": "A5"},
    ).json()
    mismatched = client.post(
        "/api/v1/job-profile-versions",
        headers=_headers(),
        json={
            "profile_key": "TIMEKEEPING_DAY",
            "version": 1,
            "display_name": "计时工",
            "core_layout": "TIMEKEEPING",
            "template_version_id": created["version_id"],
            "template_version": 99,
        },
    )
    conflict = client.post(
        f"/api/v1/job-profile-versions/{mismatched.json()['profile_version_id']}/publish",
        headers=_headers(),
    )

    assert missing.status_code == 404
    assert missing.json()["code"] == "JOB_PROFILE_NOT_FOUND"
    assert forbidden.status_code == 403
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "JOB_PROFILE_BINDING_INVALID"


def test_template_field_routes_return_field_not_found_for_unknown_fields(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"},
    )
    version_id = created.json()["version_id"]
    missing_field = _field()
    missing_field["field_key"] = "missing_field"

    patched = client.patch(
        f"/api/v1/template-versions/{version_id}/fields/missing_field",
        headers=_headers(),
        json=missing_field,
    )
    deleted = client.delete(
        f"/api/v1/template-versions/{version_id}/fields/missing_field", headers=_headers()
    )

    assert patched.status_code == 404
    assert patched.json()["code"] == "FIELD_NOT_FOUND"
    assert deleted.status_code == 404
    assert deleted.json()["code"] == "FIELD_NOT_FOUND"
