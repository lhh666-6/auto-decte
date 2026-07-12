"""RFC 9457-style error payloads without internal traceback leakage."""

from pydantic import BaseModel


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    request_id: str
