"""Phase 7 guarantees that the retired recognition product is unreachable."""

from pathlib import Path

from app.api.main_ds import create_app
from app.services.container import build_services
from config.settings import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RETIRED_PREFIXES = {
    "/api/v1/imports",
    "/api/v1/classification",
    "/api/v1/reviews",
    "/api/v1/workbench",
    "/api/v1/templates",
    "/api/v1/tasks",
    "/api/v1/exports",
}


def test_retired_desktop_api_routes_are_not_registered(tmp_path: Path) -> None:
    app = create_app(build_services(Settings(data_root=tmp_path)))
    paths = set(app.openapi()["paths"])
    for prefix in RETIRED_PREFIXES:
        assert not any(path == prefix or path.startswith(f"{prefix}/") for path in paths)


def test_old_desktop_navigation_and_routes_are_absent() -> None:
    router = (PROJECT_ROOT / "frontend/apps/web/src/app/router.tsx").read_text(
        encoding="utf-8"
    )
    for retired in (
        "ReviewWorkbenchPage",
        "TemplateStudio",
        "MasterDataCenter",
        "ExportCenter",
        'path="workbench',
        'path="templates',
        'path="master-data',
    ):
        assert retired not in router


def test_retirement_migration_and_cleanup_tool_are_present() -> None:
    migration = PROJECT_ROOT / "alembic/versions/027_retire_legacy_recognition_ds.py"
    cleanup = PROJECT_ROOT / "scripts/retire_legacy_recognition.py"
    assert migration.exists()
    assert cleanup.exists()
    source = cleanup.read_text(encoding="utf-8")
    assert "sqlite3.Connection.backup" in source
    assert "--apply" in source
