"""Task HTTP DTOs."""

from pydantic import BaseModel


class TaskCreateRequest(BaseModel):
    operation: str
    resource_id: str
    payload: dict[str, object] = {}
