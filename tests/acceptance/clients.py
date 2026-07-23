"""Recorded FastAPI TestClient wrapper."""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from .diagnostics import sanitize
from .recorder import Step


class RecordedClient:
    def __init__(self, client: TestClient, actor: str, channel: str) -> None:
        self.client = client
        self.actor = actor
        self.channel = channel

    def request(
        self,
        step: Step,
        method: str,
        path: str,
        *,
        expected_status: int | Iterable[int] | None = None,
        **kwargs: Any,
    ) -> Response:
        headers = dict(kwargs.get("headers") or {})
        request_payload = {
            "method": method.upper(),
            "path": path,
            "params": kwargs.get("params"),
            "json": kwargs.get("json"),
            "data": kwargs.get("data"),
            "headers": headers,
            "csrf_present": any(key.lower() == "x-csrf-token" for key in headers),
            "idempotency_key_present": any(
                key.lower() == "idempotency-key" for key in headers
            ),
        }
        step.capture_request(request_payload)
        started = time.perf_counter()
        response = self.client.request(method, path, **kwargs)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            body: Any = response.json()
        except ValueError:
            content_type = response.headers.get("content-type", "")
            body = (
                f"<binary:{len(response.content)}>"
                if "spreadsheet" in content_type or "octet-stream" in content_type
                else response.text[:4000]
            )
        step.capture_response(
            {
                "status_code": response.status_code,
                "headers": {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() not in {"set-cookie", "authorization"}
                },
                "body": sanitize(body),
                "duration_ms": elapsed_ms,
            }
        )
        if expected_status is not None:
            allowed = (
                {expected_status}
                if isinstance(expected_status, int)
                else set(expected_status)
            )
            if response.status_code not in allowed:
                raise AssertionError(
                    f"{method.upper()} {path}: expected HTTP {sorted(allowed)}, "
                    f"got {response.status_code}; body={sanitize(body)!r}"
                )
        return response

    def get(self, step: Step, path: str, **kwargs: Any) -> Response:
        return self.request(step, "GET", path, **kwargs)

    def post(self, step: Step, path: str, **kwargs: Any) -> Response:
        return self.request(step, "POST", path, **kwargs)
