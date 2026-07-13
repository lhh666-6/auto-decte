"""Review HTTP DTOs."""

from pydantic import BaseModel, Field


class ConfirmRequest(BaseModel):
    expected_version: int = Field(ge=0)
    lease_token: str
    values: dict[str, object]
    reason: str
    evidence_ids: list[str] = []


class LeaseResponse(BaseModel):
    form_id: str
    owner_id: str
    lease_token: str
    expires_at: str


class LeaseTokenRequest(BaseModel):
    lease_token: str = Field(min_length=1)


class ForceReleaseRequest(BaseModel):
    reason: str = Field(min_length=1)
