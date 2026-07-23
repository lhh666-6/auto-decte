"""Step-level acceptance recorder with Markdown and JSON output."""

from __future__ import annotations

import json
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .diagnostics import extract_project_traceback, locate_problem_code, sanitize


@dataclass(slots=True)
class StepState:
    step_id: str
    name: str
    actor: str
    channel: str
    started_at: float = field(default_factory=time.perf_counter)
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    result: str = "RUNNING"
    duration_ms: int = 0
    failure: dict[str, Any] | None = None


class Step(AbstractContextManager["Step"]):
    def __init__(self, recorder: ScenarioRecorder, state: StepState) -> None:
        self.recorder = recorder
        self.state = state

    def __enter__(self) -> Step:
        self.recorder.current_step = self
        return self

    def attach(self, **metadata: Any) -> None:
        self.state.metadata.update(sanitize(metadata))
        self.recorder.remember_ids(metadata)

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    def capture_request(self, payload: dict[str, Any]) -> None:
        self.state.request = sanitize(payload)

    def capture_response(self, payload: dict[str, Any]) -> None:
        self.state.response = sanitize(payload)
        self.recorder.remember_ids(payload)

    def __exit__(self, error_type: object, error: BaseException | None, tb: object) -> bool:
        self.state.duration_ms = int((time.perf_counter() - self.state.started_at) * 1000)
        if error is None:
            self.state.result = "PASSED"
        else:
            self.state.result = "FAILED"
            diagnostic = extract_project_traceback(error, self.recorder.repo_root)
            problem_code = None
            if self.state.response:
                raw = self.state.response.get("body")
                if isinstance(raw, dict):
                    candidate = raw.get("code")
                    if isinstance(candidate, str):
                        problem_code = candidate
            diagnostic["problem_code_locations"] = locate_problem_code(
                self.recorder.repo_root, problem_code
            )
            self.state.failure = diagnostic
            self.recorder.failures.append(
                {
                    "scenario": self.recorder.scenario,
                    "step_id": self.state.step_id,
                    "step_name": self.state.name,
                    "actor": self.state.actor,
                    "channel": self.state.channel,
                    "request": self.state.request,
                    "response": self.state.response,
                    "metadata": self.state.metadata,
                    **diagnostic,
                }
            )
        self.recorder.steps.append(self.state)
        self.recorder.write_step(self.state)
        self.recorder.current_step = None
        return False


class ScenarioRecorder:
    def __init__(self, scenario: str, artifact_dir: Path, repo_root: Path) -> None:
        self.scenario = scenario
        self.artifact_dir = artifact_dir
        self.repo_root = repo_root
        self.steps: list[StepState] = []
        self.failures: list[dict[str, Any]] = []
        self.current_step: Step | None = None
        self.known_ids: dict[str, set[str]] = {}
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def step(self, step_id: str, name: str, actor: str, channel: str) -> Step:
        return Step(
            self,
            StepState(
                step_id=step_id,
                name=name,
                actor=actor,
                channel=channel,
            ),
        )

    def remember_ids(self, payload: Any) -> None:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(value, str) and (
                    key.endswith("_id")
                    or key in {"record_id", "submission_id", "batch_id", "item_id"}
                ):
                    self.known_ids.setdefault(key, set()).add(value)
                else:
                    self.remember_ids(value)
        elif isinstance(payload, (list, tuple)):
            for item in payload:
                self.remember_ids(item)

    def write_step(self, state: StepState) -> None:
        path = self.artifact_dir / "steps.jsonl"
        payload = {
            "scenario": self.scenario,
            "step_id": state.step_id,
            "step_name": state.name,
            "actor": state.actor,
            "channel": state.channel,
            "request": state.request,
            "response": state.response,
            "metadata": state.metadata,
            "result": state.result,
            "duration_ms": state.duration_ms,
            "failure": state.failure,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sanitize(payload), ensure_ascii=False) + "\n")

    def record_outside_step_failure(self, error: BaseException) -> None:
        diagnostic = extract_project_traceback(error, self.repo_root)
        self.failures.append(
            {
                "scenario": self.scenario,
                "step_id": "PYTEST",
                "step_name": "测试框架或步骤外异常",
                "actor": "UNKNOWN",
                "channel": "LOCAL",
                **diagnostic,
            }
        )

    def finalize(self) -> None:
        failures_path = self.artifact_dir / "failures.json"
        failures_path.write_text(
            json.dumps(sanitize(self.failures), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        traceback_text = "\n\n".join(
            str(item.get("traceback", "")) for item in self.failures
        )
        (self.artifact_dir / "traceback.txt").write_text(
            traceback_text or "No traceback captured.\n",
            encoding="utf-8",
        )
        summary = {
            "scenario": self.scenario,
            "total_steps": len(self.steps),
            "passed_steps": sum(step.result == "PASSED" for step in self.steps),
            "failed_steps": sum(step.result == "FAILED" for step in self.steps),
            "failures": len(self.failures),
            "known_ids": {key: sorted(values) for key, values in self.known_ids.items()},
        }
        (self.artifact_dir / "scenario-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
