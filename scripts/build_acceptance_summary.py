"""Aggregate per-scenario acceptance artifacts into one Markdown report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_dir", type=Path)
    args = parser.parse_args()
    artifact_dir: Path = args.artifact_dir
    scenarios_dir = artifact_dir / "scenarios"
    summaries = [
        load_json(path, {})
        for path in sorted(scenarios_dir.glob("*/scenario-summary.json"))
    ]
    failures: list[dict[str, Any]] = []
    for path in sorted(scenarios_dir.glob("*/failures.json")):
        payload = load_json(path, [])
        if isinstance(payload, list):
            failures.extend(item for item in payload if isinstance(item, dict))

    total_steps = sum(int(item.get("total_steps", 0)) for item in summaries)
    passed_steps = sum(int(item.get("passed_steps", 0)) for item in summaries)
    failed_steps = sum(int(item.get("failed_steps", 0)) for item in summaries)
    lines = [
        "# 自动诊断验收报告",
        "",
        f"- 场景数：{len(summaries)}",
        f"- 总步骤：{total_steps}",
        f"- 通过步骤：{passed_steps}",
        f"- 失败步骤：{failed_steps}",
        f"- 失败记录：{len(failures)}",
        "",
        "## 场景结果",
        "",
        "| 场景 | 步骤 | 通过 | 失败 |",
        "|---|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            f"| `{item.get('scenario', 'unknown')}` | "
            f"{item.get('total_steps', 0)} | "
            f"{item.get('passed_steps', 0)} | "
            f"{item.get('failed_steps', 0)} |"
        )

    lines.extend(["", "## 失败位置", ""])
    if not failures:
        lines.append("未捕获失败。")
    for index, failure in enumerate(failures, 1):
        response = failure.get("response") or {}
        body = response.get("body") if isinstance(response, dict) else {}
        code = body.get("code") if isinstance(body, dict) else None
        selected = failure.get("selected_location") or {}
        lines.extend(
            [
                f"### {index}. {failure.get('step_name', '未知步骤')}",
                "",
                f"- 场景：`{failure.get('scenario', 'unknown')}`",
                f"- 身份：`{failure.get('actor', 'UNKNOWN')}`",
                f"- 渠道：`{failure.get('channel', 'UNKNOWN')}`",
                f"- HTTP：`{(failure.get('request') or {}).get('method', '')} "
                f"{(failure.get('request') or {}).get('path', '')}`",
                f"- 状态：`{response.get('status_code', '')}`",
                f"- Problem code：`{code or ''}`",
                f"- 异常：`{failure.get('exception_type', '')}: "
                f"{failure.get('exception_message', '')}`",
                f"- 测试/项目位置：`{selected.get('file', '')}:"
                f"{selected.get('line', '')}` `{selected.get('function', '')}`",
                "",
            ]
        )
        locations = failure.get("problem_code_locations") or []
        if locations:
            lines.append("可能的后端错误码位置：")
            for location in locations[:8]:
                lines.append(
                    f"- `{location.get('file')}:{location.get('line')}` "
                    f"`{location.get('code')}`"
                )
            lines.append("")
        lines.append(
            "相关数据库现场："
            f"`scenarios/{failure.get('scenario', 'unknown')}/database-snapshot.json`"
        )
        lines.append("")

    (artifact_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (artifact_dir / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
