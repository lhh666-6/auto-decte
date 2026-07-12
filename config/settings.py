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
    task_max_workers: int = 2
    task_queue_capacity: int = 32
    review_lease_seconds: int = 300
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    local_default_user_id: str = "local-operator"
    local_default_roles: tuple[str, ...] = ("OPERATOR",)

    @property
    def database_path(self) -> Path:
        return self.data_root / "database" / "demo.db"

    @property
    def evidence_root(self) -> Path:
        return self.data_root / "evidence"

    @property
    def exports_root(self) -> Path:
        return self.data_root / "exports"
