"""Guard against reintroducing process-local mobile pilot state."""

from pathlib import Path


def test_production_mobile_code_contains_no_demo_identity_or_process_store() -> None:
    root = Path(__file__).resolve().parents[2]
    sources = [
        *sorted((root / "app" / "api" / "routers").glob("mobile*_ds.py")),
        root / "app" / "application" / "mobile_identity_ds.py",
        *sorted(
            path
            for path in (root / "frontend" / "apps" / "web" / "src" / "mobile").rglob("*")
            if path.suffix in {".ts", ".tsx"} and ".test." not in path.name
        ),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    forbidden = (
        "_PILOT_USERS",
        "_SESSIONS",
        "_form_schemas",
        "mobile_token",
        "Bearer ${",
        "张三",
        "李四",
    )

    for marker in forbidden:
        assert marker not in combined

    assert not (root / "app" / "modules" / "mobile" / "models_ds.py").exists()
    assert not (root / "frontend" / "apps" / "web" / "src" / "mobile" / "api.ts").exists()
    assert not (root / "frontend" / "apps" / "web" / "src" / "mobile" / "auth.ts").exists()
