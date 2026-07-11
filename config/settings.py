"""Environment-driven application settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with all generated data below one root."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FORM_DEMO_",
        extra="ignore",
    )

    data_root: Path = Path("data")
    ai_enabled: bool = False

    @property
    def database_path(self) -> Path:
        return self.data_root / "database" / "demo.db"

    @property
    def evidence_root(self) -> Path:
        return self.data_root / "evidence"

    @property
    def exports_root(self) -> Path:
        return self.data_root / "exports"
