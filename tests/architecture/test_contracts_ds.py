"""Architecture contract tests for the modular monolith."""

from pathlib import Path


def test_domain_does_not_import_frameworks() -> None:
    """Domain layer must not depend on FastAPI, SQLAlchemy, or Streamlit."""
    domain_source = Path("app/domain")
    for path in sorted(domain_source.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for framework in ("fastapi", "sqlalchemy", "streamlit"):
            assert framework not in source.lower(), (
                f"{path} imports {framework}"
            )


def test_api_routers_use_ds_suffix() -> None:
    """All API router files should use _ds suffix."""
    router_dir = Path("app/api/routers")
    for path in router_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        assert path.stem.endswith("_ds"), f"{path} does not end with _ds"


def test_module_facades_use_ds_suffix() -> None:
    """All module facade files should use _ds suffix."""
    modules_dir = Path("app/modules")
    for path in sorted(modules_dir.rglob("facade*.py")):
        assert path.stem.endswith("_ds"), f"{path} does not end with _ds"


def test_all_module_dirs_have_init() -> None:
    """Every module directory must have an __init__.py."""
    modules_dir = Path("app/modules")
    for subdir in sorted(modules_dir.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("_"):
            init_file = subdir / "__init__.py"
            assert init_file.exists(), f"Missing {init_file}"


def test_infrastructure_files_use_ds_suffix() -> None:
    """All infrastructure source files (except __init__) should use _ds suffix."""
    infra_dir = Path("app/infrastructure")
    for path in sorted(infra_dir.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        if path.name == "__init__ds.py":
            continue
        assert path.stem.endswith("_ds"), f"{path} does not end with _ds"


def test_config_has_modular_settings() -> None:
    """Settings must include modular architecture fields."""
    from config.settings import Settings  # type: ignore[import-untyped]

    settings = Settings()
    assert hasattr(settings, "task_max_workers")
    assert hasattr(settings, "review_lease_seconds")
    assert hasattr(settings, "api_host")
    assert hasattr(settings, "api_port")
    assert hasattr(settings, "local_default_user_id")
    assert hasattr(settings, "local_default_roles")
