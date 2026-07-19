"""Review HTTP DTOs."""

from typing import Literal

from pydantic import BaseModel, Field


class ConfirmRequest(BaseModel):
    expected_version: int = Field(ge=0)
    lease_token: str
    values: dict[str, object]
    reason: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(default_factory=list)
    manually_confirmed_field_keys: list[str] = Field(default_factory=list)


class ConfirmAndClaimNextRequest(ConfirmRequest):
    queue_key: Literal["review"] = "review"


class SaveDraftRequest(BaseModel):
    expected_version: int = Field(ge=0)
    lease_token: str = Field(min_length=1)
    values: dict[str, object]


class ReviewActionRequest(BaseModel):
    expected_version: int = Field(ge=0)
    lease_token: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(default_factory=list)


class LeaseResponse(BaseModel):
    form_id: str
    owner_id: str
    lease_token: str
    expires_at: str


class LeaseTokenRequest(BaseModel):
    lease_token: str = Field(min_length=1)


class ForceReleaseRequest(BaseModel):
    reason: str = Field(min_length=1)
