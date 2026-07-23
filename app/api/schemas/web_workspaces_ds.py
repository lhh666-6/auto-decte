"""HTTP schemas for Web authentication and workspace overviews."""

from pydantic import BaseModel, Field


class WebLoginRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=64)
    pin: str = Field(min_length=4, max_length=32)
    device_id: str = Field(default="web-browser", min_length=1, max_length=128)


class WebSessionResponse(BaseModel):
    employee_code: str
    employee_name: str
    workspace_role: str
    workspace_roles: list[str]
    factory_id: str = ""
    factory_name: str = ""
    landing_path: str


class OverviewCard(BaseModel):
    key: str
    label: str
    value: int = 0


class WorkspaceOverviewResponse(BaseModel):
    workspace: str
    title: str
    scope: str
    factory_id: str = ""
    factory_name: str = ""
    cards: list[OverviewCard] = Field(default_factory=list)
