"""Phase 0 contracts for the Web transformation boundary."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

from app.api.routers import (
    mobile_auth_ds,
    mobile_bamboo_ds,
    mobile_context_ds,
    mobile_definitions_ds,
    mobile_submissions_ds,
)
from app.api.routers.mobile_ds import router as mobile_router
from app.api.schemas import bamboo_process_ds, mobile_ds

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "c05349fd6b3423f51e2774f68a3027612fcf806d"
MOBILE_PATH = "frontend/apps/web/src/mobile"

TARGET_MODULES = {
    "admin_console",
    "audit",
    "business_discovery",
    "business_knowledge",
    "data_lineage",
    "electronic_forms",
    "finance_ledger",
    "identity_access",
    "notifications",
    "payroll_rules",
    "report_templates",
    "reporting",
    "secret_config",
    "submission_ledger",
    "workflow_engine",
}

EXPECTED_SCHEMA_FIELDS = {
    mobile_ds.LoginRequest: {"device_id", "employee_code", "pin"},
    mobile_ds.LoginResponse: {
        "bamboo_role",
        "employee_code",
        "employee_name",
        "expires_at",
        "factory_id",
        "factory_name",
        "position",
        "roles",
        "team_name",
    },
    mobile_ds.SessionResponse: {
        "allowed_form_types",
        "allowed_processes",
        "bamboo_role",
        "employee_code",
        "employee_name",
        "factory_id",
        "factory_name",
        "position",
        "roles",
        "team_name",
    },
    mobile_ds.CreateSubmissionRequest: {
        "definition_version_id",
        "device_id",
        "form_type",
        "mode",
        "subject_employee_code",
        "values",
    },
    mobile_ds.SubmissionResponse: {
        "idempotent",
        "status",
        "submission_id",
        "submitted_at",
    },
    mobile_ds.FormSchemaResponse: {
        "definition_version_id",
        "fields",
        "form_type",
        "modes",
        "title",
        "version",
    },
    bamboo_process_ds.CreateBambooRecordRequest: {"base_info", "form_type"},
    bamboo_process_ds.SubmitBambooStageRequest: {
        "device_id",
        "expected_revision",
        "values",
    },
}

EXPECTED_MOBILE_ROUTES = {
    "GET /api/v1/mobile/active-resources",
    "GET /api/v1/mobile/auth/session",
    "GET /api/v1/mobile/available-forms",
    "GET /api/v1/mobile/bamboo/admin/employees",
    "GET /api/v1/mobile/bamboo/dashboard",
    "GET /api/v1/mobile/bamboo/factories",
    "GET /api/v1/mobile/bamboo/finance/daily-batches",
    "GET /api/v1/mobile/bamboo/finance/export.xlsx",
    "GET /api/v1/mobile/bamboo/finance/inquiries",
    "GET /api/v1/mobile/bamboo/finance/monthly-summary",
    "GET /api/v1/mobile/bamboo/history",
    "GET /api/v1/mobile/bamboo/inspection-queue",
    "GET /api/v1/mobile/bamboo/notifications",
    "GET /api/v1/mobile/bamboo/payroll-rules",
    "GET /api/v1/mobile/bamboo/personnel-transfers",
    "GET /api/v1/mobile/bamboo/record-options",
    "GET /api/v1/mobile/bamboo/records/{record_id}",
    "GET /api/v1/mobile/bamboo/records/{record_id}/operations",
    "GET /api/v1/mobile/bamboo/role-change-requests",
    "GET /api/v1/mobile/bamboo/role-options",
    "GET /api/v1/mobile/bamboo/tasks",
    "GET /api/v1/mobile/context",
    "GET /api/v1/mobile/form-schemas/{form_type}",
    "GET /api/v1/mobile/options/{catalog}",
    "GET /api/v1/mobile/production-contexts/current",
    "GET /api/v1/mobile/submissions",
    "GET /api/v1/mobile/team-members",
    "POST /api/v1/mobile/auth/login",
    "POST /api/v1/mobile/auth/logout",
    "POST /api/v1/mobile/bamboo/admin/assignments",
    "POST /api/v1/mobile/bamboo/admin/employees",
    "POST /api/v1/mobile/bamboo/admin/factories",
    "POST /api/v1/mobile/bamboo/finance/inquiries/{inquiry_id}/reply",
    "POST /api/v1/mobile/bamboo/finance/items/{item_id}/decision",
    "POST /api/v1/mobile/bamboo/finance/items/{item_id}/inquiries",
    "POST /api/v1/mobile/bamboo/inspection-exceptions/{exception_id}/close",
    "POST /api/v1/mobile/bamboo/inspection-queue/{record_id}/appeal",
    "POST /api/v1/mobile/bamboo/inspection-queue/{record_id}/appeal/claim",
    "POST /api/v1/mobile/bamboo/inspection-queue/{record_id}/appeal/decision",
    "POST /api/v1/mobile/bamboo/inspection-queue/{record_id}/claim",
    "POST /api/v1/mobile/bamboo/inspection-queue/{record_id}/terminate",
    "POST /api/v1/mobile/bamboo/inspections/{inspection_id}/evidence",
    "POST /api/v1/mobile/bamboo/notifications/{notification_id}/read",
    "POST /api/v1/mobile/bamboo/payroll-rules",
    "POST /api/v1/mobile/bamboo/personnel-transfers",
    "POST /api/v1/mobile/bamboo/personnel-transfers/{transfer_id}/execute",
    "POST /api/v1/mobile/bamboo/personnel-transfers/{transfer_id}/manager-decision",
    "POST /api/v1/mobile/bamboo/records",
    "POST /api/v1/mobile/bamboo/records/{record_id}/inspection-submit",
    "POST /api/v1/mobile/bamboo/records/{record_id}/inspections",
    "POST /api/v1/mobile/bamboo/records/{record_id}/return",
    "POST /api/v1/mobile/bamboo/records/{record_id}/stages/{stage_key}/submit",
    "POST /api/v1/mobile/bamboo/role-change-requests",
    "POST /api/v1/mobile/bamboo/role-change-requests/{role_request_id}/decision",
    "POST /api/v1/mobile/submissions",
}


def _registered_mobile_routes() -> set[str]:
    routers = (
        mobile_auth_ds.router,
        mobile_bamboo_ds.router,
        mobile_context_ds.router,
        mobile_definitions_ds.router,
        mobile_submissions_ds.router,
    )
    return {
        f"{method} {mobile_router.prefix}{route.path}"
        for router in routers
        for route in router.routes
        for method in route.methods
    }


def test_mobile_router_aggregation_is_frozen() -> None:
    included = [
        entry.original_router
        for entry in mobile_router.routes
        if hasattr(entry, "original_router")
    ]
    assert included == [
        mobile_auth_ds.router,
        mobile_bamboo_ds.router,
        mobile_definitions_ds.router,
        mobile_context_ds.router,
        mobile_submissions_ds.router,
    ]
    assert _registered_mobile_routes() == EXPECTED_MOBILE_ROUTES


def test_shared_mobile_schema_fields_are_frozen() -> None:
    for schema, expected_fields in EXPECTED_SCHEMA_FIELDS.items():
        assert set(schema.model_fields) == expected_fields


def test_target_module_boundaries_are_importable() -> None:
    for module_name in TARGET_MODULES:
        importlib.import_module(f"app.modules.{module_name}")


def test_root_modules_package_has_no_eager_registration() -> None:
    source = (PROJECT_ROOT / "app" / "modules" / "__init__.py").read_text(encoding="utf-8")
    assert source.strip() == '"""Module facades that expose stable application boundaries."""'


def test_boundary_script_exposes_base_and_head_arguments() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_mobile_boundary.py", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--base" in result.stdout
    assert "--head" in result.stdout


def test_boundary_script_classifies_only_mobile_paths() -> None:
    from scripts import check_mobile_boundary

    changed = check_mobile_boundary.mobile_changes(
        [
            "frontend/apps/web/src/mobile/MobileApp.tsx",
            "frontend/apps/web/src/admin/AdminApp.tsx",
            r"frontend\apps\web\src\mobile\Profile.tsx",
        ]
    )
    assert changed == {
        "frontend/apps/web/src/mobile/MobileApp.tsx",
        "frontend/apps/web/src/mobile/Profile.tsx",
    }


def test_boundary_script_fails_closed_when_git_diff_fails() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_mobile_boundary.py",
            "--base",
            "missing-phase-0-ref",
            "--head",
            "HEAD",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "boundary check failed" in result.stderr.lower()


def test_ci_calls_the_tested_boundary_script_and_contract_suite() -> None:
    workflow = (
        PROJECT_ROOT / ".github" / "workflows" / "web-transformation-boundary.yml"
    ).read_text(encoding="utf-8")
    assert "python scripts/check_mobile_boundary.py" in workflow
    assert "tests/architecture/test_web_transformation_phase_0_ds.py" in workflow


def test_phase_0_document_uses_real_baseline_and_complete_route_count() -> None:
    document = (
        PROJECT_ROOT / "docs" / "architecture" / "web-transformation-phase-0.md"
    ).read_text(encoding="utf-8")
    assert BASELINE_COMMIT in document
    assert "55 个移动端端点" in document
    assert "15 个现有业务模块" in document


def test_current_branch_has_not_changed_mobile_sources() -> None:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            BASELINE_COMMIT,
            "HEAD",
            "--",
            MOBILE_PATH,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == ""
