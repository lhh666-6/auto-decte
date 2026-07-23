"""Phase 6 report mapping and export requests."""

from typing import Any

from pydantic import BaseModel, Field


class CreateReportMappingRequest(BaseModel):
    template_version_id: str
    mapping_json: dict[str, Any]


class CreateGovernedExportRequest(BaseModel):
    template_version_id: str
    mapping_version_id: str
    filters: dict[str, Any] = {}
    idempotency_key: str = Field(min_length=1, max_length=200)
