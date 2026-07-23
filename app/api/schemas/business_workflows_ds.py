"""Phase 3 business discovery and workflow contracts."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateDiscoverySessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    source_refs: list[str] = Field(default_factory=list)


class DiscoveryMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class ConfirmDiscoveryRequest(BaseModel):
    rule_ids: list[str] = Field(min_length=1)
    note: str = Field(default="", max_length=1000)


class CreateWorkflowRequest(BaseModel):
    workflow_key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=160)
    graph_json: dict[str, Any]
    canvas_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowApprovalDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"]


class WorkflowActivationRequest(BaseModel):
    plant_ids: list[str] = Field(min_length=1)
