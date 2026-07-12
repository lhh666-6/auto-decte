"""Tests for the observability infrastructure (logging + error tracking)."""

import json
import logging
import sys

from app.infrastructure.observability.error_tracker_ds import LocalErrorTracker
from app.infrastructure.observability.logging_ds import JsonLogFormatter

# ---------------------------------------------------------------------------
# JsonLogFormatter
# ---------------------------------------------------------------------------


def test_json_log_formatter_outputs_required_fields() -> None:
    """The JsonLogFormatter produces valid JSON with timestamp, level, and message."""
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    raw = formatter.format(record)
    payload = json.loads(raw)

    assert payload["timestamp"] is not None
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test_logger"
    assert payload["message"] == "hello world"


def test_json_log_formatter_includes_extra_fields() -> None:
    """Extra fields (request_id, actor_id, module, event, …) appear in the output."""
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=20,
        msg="operation completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-001"
    record.actor_id = "user-42"
    record.module = "review"
    record.event = "form.confirmed"
    record.operation = "confirm"
    record.form_id = "FORM-001"
    record.task_id = "TASK-007"
    record.duration_ms = 123
    record.result = "success"

    raw = formatter.format(record)
    payload = json.loads(raw)

    assert payload["request_id"] == "req-001"
    assert payload["actor_id"] == "user-42"
    assert payload["module"] == "review"
    assert payload["event"] == "form.confirmed"
    assert payload["operation"] == "confirm"
    assert payload["form_id"] == "FORM-001"
    assert payload["task_id"] == "TASK-007"
    assert payload["duration_ms"] == 123
    assert payload["result"] == "success"


def test_json_log_formatter_omits_none_extra_fields() -> None:
    """Extra fields that are not set on the record are omitted from the output."""
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=30,
        msg="no extras",
        args=(),
        exc_info=None,
    )
    raw = formatter.format(record)
    payload = json.loads(raw)

    assert "request_id" not in payload
    assert "actor_id" not in payload
    assert "error_code" not in payload


def test_json_log_formatter_includes_exception_info() -> None:
    """Exception type and message are included when exc_info is set."""
    formatter = JsonLogFormatter()
    try:
        raise ValueError("something went wrong")
    except ValueError:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=40,
            msg="operation failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    raw = formatter.format(record)
    payload = json.loads(raw)

    assert payload["level"] == "ERROR"
    assert payload["exception"]["type"] == "ValueError"
    assert payload["exception"]["message"] == "something went wrong"


def test_json_log_formatter_includes_error_code() -> None:
    """The optional error_code field is included when set."""
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=50,
        msg="validation failed",
        args=(),
        exc_info=None,
    )
    record.error_code = "VALIDATION_ERROR"

    raw = formatter.format(record)
    payload = json.loads(raw)

    assert payload["error_code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# LocalErrorTracker
# ---------------------------------------------------------------------------


def test_error_tracker_records_and_retrieves_errors() -> None:
    """record() stores an error and all() returns it."""
    tracker = LocalErrorTracker()
    error = ValueError("invalid quantity")

    record = tracker.record(error, module="rules", operation="validate")

    assert record.error_type == "ValueError"
    assert record.message == "invalid quantity"
    assert record.module == "rules"
    assert record.operation == "validate"
    assert record.form_id is None

    all_errors = tracker.all
    assert len(all_errors) == 1
    assert all_errors[0] is record


def test_error_tracker_records_context_fields() -> None:
    """record() stores all optional context fields."""
    tracker = LocalErrorTracker()
    error = RuntimeError("timeout")

    record = tracker.record(
        error,
        module="recognition",
        operation="classify",
        form_id="FORM-001",
        task_id="TASK-123",
        actor_id="user-5",
        details={"image_size": (1920, 1080)},
    )

    assert record.form_id == "FORM-001"
    assert record.task_id == "TASK-123"
    assert record.actor_id == "user-5"
    assert record.details == {"image_size": (1920, 1080)}


def test_error_tracker_count() -> None:
    """count returns the number of recorded errors."""
    tracker = LocalErrorTracker()
    assert tracker.count == 0

    tracker.record(ValueError("e1"), module="m", operation="o")
    assert tracker.count == 1

    tracker.record(RuntimeError("e2"), module="m", operation="o")
    assert tracker.count == 2


def test_error_tracker_clear() -> None:
    """clear() removes all recorded errors."""
    tracker = LocalErrorTracker()
    tracker.record(ValueError("e1"), module="m", operation="o")
    tracker.record(RuntimeError("e2"), module="m", operation="o")
    assert tracker.count == 2

    tracker.clear()
    assert tracker.count == 0
    assert tracker.all == []


def test_error_tracker_all_returns_copy() -> None:
    """all() returns a copy so mutating it does not affect the tracker."""
    tracker = LocalErrorTracker()
    tracker.record(ValueError("e1"), module="m", operation="o")

    snapshot = tracker.all
    snapshot.clear()

    assert tracker.count == 1


def test_error_tracker_by_module() -> None:
    """by_module() filters errors by module name."""
    tracker = LocalErrorTracker()
    tracker.record(ValueError("e1"), module="rules", operation="validate")
    tracker.record(RuntimeError("e2"), module="recognition", operation="classify")
    tracker.record(ValueError("e3"), module="rules", operation="validate")

    rules_errors = tracker.by_module("rules")
    assert len(rules_errors) == 2

    recog_errors = tracker.by_module("recognition")
    assert len(recog_errors) == 1

    unknown_errors = tracker.by_module("unknown")
    assert unknown_errors == []


def test_error_tracker_timestamp_is_set() -> None:
    """Each recorded error has a non-None timestamp."""
    tracker = LocalErrorTracker()
    record = tracker.record(ValueError("e1"), module="m", operation="o")
    assert record.timestamp is not None
