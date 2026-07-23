"""Phase 4 finance-ledger and correction requests."""

from pydantic import BaseModel, Field


class ReturnSubmissionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    assigned_to: str = Field(min_length=1, max_length=100)


class AttachReplacementRequest(BaseModel):
    replacement_submission_id: str = Field(min_length=1, max_length=100)
    actual_actor_id: str = Field(min_length=1, max_length=100)
    delegate_reason: str = Field(default="", max_length=500)


class ReviewCorrectionRequest(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=500)
