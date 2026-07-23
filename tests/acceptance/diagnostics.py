"""Local-only diagnostic helpers for acceptance tests."""

from __future__ import annotations

import json
import re
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, inspect, text

SENSITIVE_KEYS = {
    "pin",
    "password",
    "authorization",
    "cookie",
    "set-cookie",
    "x-csrf-token",
    "csrf",
    "csrf_token",
    "api_key",
    "deepseek_api_key",
    "token",
    "session",
}

INTERESTING_TABLE_TOKENS = (
    "bamboo",
    "mobile_",
    "master_data",
    "employee_",
)


def sanitize(value: Any, *, key: str = "") -> Any:
    """Recursively remove secrets while keeping a useful diagnostic shape."""
    lowered = key.lower().replace("-", "_")
    if any(token.replace("-", "_") in lowered for token in SENSITIVE_KEYS):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            str(item_key): sanitize(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize(item) for item in value]
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def extract_project_traceback(error: BaseException, repo_root: Path) -> dict[str, Any]:
    """Return the most relevant project stack frames for a local report."""
    frames = traceback.extract_tb(error.__traceback__)
    normalized_root = repo_root.resolve()
    project_frames: list[dict[str, Any]] = []
    for frame in frames:
        path = Path(frame.filename).resolve()
        try:
            relative = path.relative_to(normalized_root)
        except ValueError:
            continue
        if any(part in {"site-packages", ".venv"} for part in relative.parts):
            continue
        project_frames.append(
            {
                "file": relative.as_posix(),
                "line": frame.lineno,
                "function": frame.name,
                "code": frame.line,
            }
        )
    selected = project_frames[-1] if project_frames else None
    return {
        "exception_type": type(error).__name__,
        "exception_message": str(error),
        "selected_location": selected,
        "project_frames": project_frames,
        "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
    }


def locate_problem_code(repo_root: Path, code: str | None) -> list[dict[str, Any]]:
    """Find likely backend source locations for a FastAPI problem code."""
    if not code or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,100}", code):
        return []
    matches: list[dict[str, Any]] = []
    for base in (repo_root / "app", repo_root / "config"):
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(lines, 1):
                if code in line:
                    matches.append(
                        {
                            "file": path.relative_to(repo_root).as_posix(),
                            "line": number,
                            "code": line.strip(),
                        }
                    )
                    if len(matches) >= 20:
                        return matches
    return matches


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def snapshot_database(
    engine: Engine,
    destination: Path,
    *,
    known_ids: dict[str, set[str]] | None = None,
) -> None:
    """Capture relevant SQLite rows without copying the whole database file."""
    known_ids = known_ids or {}
    inspector = inspect(engine)
    result: dict[str, Any] = {
        "dialect": engine.dialect.name,
        "known_ids": {key: sorted(values) for key, values in known_ids.items()},
        "tables": {},
        "checks": [],
    }
    with engine.connect() as connection:
        for table_name in inspector.get_table_names():
            lowered = table_name.lower()
            if not any(token in lowered for token in INTERESTING_TABLE_TOKENS):
                continue
            columns = [column["name"] for column in inspector.get_columns(table_name)]
            where_parts: list[str] = []
            parameters: dict[str, Any] = {}
            for id_key, values in known_ids.items():
                if id_key not in columns or not values:
                    continue
                names: list[str] = []
                for index, value in enumerate(sorted(values)):
                    parameter = f"{id_key}_{index}"
                    parameters[parameter] = value
                    names.append(f":{parameter}")
                where_parts.append(f'"{id_key}" IN ({", ".join(names)})')
            sql = f'SELECT * FROM "{table_name}"'
            if where_parts:
                sql += " WHERE " + " OR ".join(where_parts)
            sql += " LIMIT 300"
            try:
                rows = connection.execute(text(sql), parameters).mappings().all()
            except Exception as error:  # diagnostics must not hide the original failure
                result["tables"][table_name] = {"error": repr(error), "rows": []}
                continue
            result["tables"][table_name] = {
                "columns": columns,
                "rows": [
                    {key: _json_value(value) for key, value in row.items()}
                    for row in rows
                ],
            }

    tables = result["tables"]
    for table_name, payload in tables.items():
        rows = payload.get("rows", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            continue
        if "submission" in table_name.lower():
            active = [row for row in rows if not bool(row.get("invalidated", False))]
            identifiers = [row.get("submission_id") for row in active if row.get("submission_id")]
            if len(identifiers) != len(set(identifiers)):
                result["checks"].append(
                    {"kind": "DUPLICATE_SUBMISSION_ID", "table": table_name}
                )
        if "signature" in table_name.lower():
            submission_ids = [
                row.get("submission_id") for row in rows if row.get("submission_id")
            ]
            if len(submission_ids) != len(set(submission_ids)):
                result["checks"].append(
                    {"kind": "DUPLICATE_SIGNATURE_FOR_SUBMISSION", "table": table_name}
                )
        if "payroll_fact" in table_name.lower():
            effective = [
                row for row in rows if row.get("status") in {"EFFECTIVE", "PENDING_EFFECTIVE"}
            ]
            keys = [
                (row.get("record_id"), row.get("fact_type"), row.get("version"))
                for row in effective
            ]
            if len(keys) != len(set(keys)):
                result["checks"].append(
                    {"kind": "DUPLICATE_PAYROLL_FACT_VERSION", "table": table_name}
                )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(sanitize(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
