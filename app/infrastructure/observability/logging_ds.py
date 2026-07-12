"""Structured JSON log formatter for observable audit trails."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonLogFormatter(logging.Formatter):
    """Output structured JSON log records with standard observability fields.

    Expected extra fields on the ``LogRecord``:

    - ``request_id``  — unique request correlation id
    - ``actor_id``    — user / system actor performing the operation
    - ``module``      — originating module name (e.g. ``"review"``)
    - ``event``       — event name (e.g. ``"form.confirmed"``)
    - ``operation``   — operation name (e.g. ``"confirm"``)
    - ``form_id``     — affected form id (if applicable)
    - ``task_id``     — affected task id (if applicable)
    - ``duration_ms`` — elapsed wall-clock milliseconds (if applicable)
    - ``result``      — result summary (e.g. ``"success"``, ``"skipped"``)
    - ``error_code``  — machine-readable error code (if applicable)
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Map standard extras
        for key in (
            "request_id",
            "actor_id",
            "module",
            "event",
            "operation",
            "form_id",
            "task_id",
            "duration_ms",
            "result",
            "error_code",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        # Include exception info if present
        exc_info = record.exc_info
        if exc_info:
            if not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()
            if exc_info and exc_info[0] is not None and exc_info[1] is not None:
                payload["exception"] = {
                    "type": exc_info[0].__name__,
                    "message": str(exc_info[1]),
                }

        return json.dumps(payload, ensure_ascii=False, default=str)
