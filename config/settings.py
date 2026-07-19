"""Environment-driven application settings."""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with all generated data below one root."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FORM_DEMO_",
        extra="ignore",
        populate_by_name=True,
    )

    data_root: Path = Path("data")
    environment: str = "development"
    auto_create_schema: bool = True
    allow_header_identity: bool = False
    ai_enabled: bool = False
    deepseek_api_key: str | None = None
    deepseek_endpoint: str = "https://api.deepseek.com/chat/completions"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: float = Field(default=20.0, gt=0, le=60)
    task_max_workers: int = 2
    task_queue_capacity: int = 32
    review_lease_seconds: int = 300
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    app_auth_mode: Literal["local_full_access", "authenticated"] = Field(
        default="local_full_access",
        validation_alias=AliasChoices("APP_AUTH_MODE", "FORM_DEMO_APP_AUTH_MODE"),
    )
    local_default_user_id: str = "local-operator"
    local_default_roles: tuple[str, ...] = ("OPERATOR",)
    cjk_font_path: Path | None = None

    @property
    def database_path(self) -> Path:
        return self.data_root / "database" / "demo.db"

    @property
    def evidence_root(self) -> Path:
        return self.data_root / "evidence"

    @property
    def exports_root(self) -> Path:
        return self.data_root / "exports"
