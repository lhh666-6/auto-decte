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
    environment: str = "development"
    auto_create_schema: bool = True
    allow_header_identity: bool = False
    ai_enabled: bool = False
    task_max_workers: int = 2
    task_queue_capacity: int = 32
    review_lease_seconds: int = 300
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # The standalone Demo must expose the complete local workflow. Production deployments
    # replace this provider with an authenticated identity adapter and explicit roles.
    local_default_user_id: str = "local-admin"
    local_default_roles: tuple[str, ...] = ("ADMIN",)

    @property
    def database_path(self) -> Path:
        return self.data_root / "database" / "demo.db"

    @property
    def evidence_root(self) -> Path:
        return self.data_root / "evidence"

    @property
    def exports_root(self) -> Path:
        return self.data_root / "exports"
