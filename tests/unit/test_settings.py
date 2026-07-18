from pathlib import Path

from config.settings import Settings


def test_settings_keep_runtime_data_below_configured_root(tmp_path: Path) -> None:
    settings = Settings(data_root=tmp_path, ai_enabled=False, _env_file=None)

    assert settings.database_path == tmp_path / "database" / "demo.db"
    assert settings.evidence_root == tmp_path / "evidence"
    assert settings.exports_root == tmp_path / "exports"
    assert settings.ai_enabled is False
    assert settings.app_auth_mode == "local_full_access"


def test_auth_mode_supports_the_documented_environment_name(monkeypatch) -> None:
    monkeypatch.setenv("APP_AUTH_MODE", "authenticated")

    settings = Settings(_env_file=None)

    assert settings.app_auth_mode == "authenticated"
