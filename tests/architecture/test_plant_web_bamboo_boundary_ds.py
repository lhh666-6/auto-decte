"""Static acceptance for the unified plant-manager Web boundary."""

from pathlib import Path


def test_plant_web_uses_bamboo_without_parallel_business_sources() -> None:
    source = Path("app/api/routers/plant_workspace_ds.py").read_text(encoding="utf-8")
    for forbidden in (
        "SubmissionLedgerService",
        "PayrollService",
        "ManagementNotification",
        "list_notifications(plant_id)",
        "/submissions/{submission_id}/return",
    ):
        assert forbidden not in source
    for required in (
        "BambooOperationsService",
        "selective_return",
        "list_notifications",
        "monthly_summary",
        "list_personnel_transfers",
    ):
        assert required in source


def test_plant_manager_mobile_boundary_is_explicit() -> None:
    source = Path("app/api/routers/mobile_bamboo_ds.py").read_text(encoding="utf-8")
    assert "PLANT_MANAGER_WEB_ONLY" in source
