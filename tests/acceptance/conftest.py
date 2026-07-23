"""Acceptance fixtures and automatic failure artifacts."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings

from .clients import RecordedClient
from .diagnostics import snapshot_database
from .recorder import ScenarioRecorder

PIN = "2468"
FACTORY_A = "ACCEPTANCE-FACTORY-A"
FACTORY_B = "ACCEPTANCE-FACTORY-B"


@dataclass(slots=True)
class AcceptanceEnvironment:
    services: Services
    recorder: ScenarioRecorder

    def add_identity(
        self,
        *,
        employee_code: str,
        employee_name: str,
        bamboo_role: str,
        factory_id: str = FACTORY_A,
        workspace_roles: list[str] | None = None,
    ) -> None:
        factory_name = "自动验收一厂" if factory_id == FACTORY_A else "自动验收二厂"
        self.services.master_data.create(
            MasterDataCatalog.EMPLOYEES,
            employee_code,
            employee_name,
            {},
            "acceptance",
            "isolated automated acceptance identity",
        )
        self.services.mobile_identity_repository.set_credential(employee_code, PIN)
        self.services.mobile_identity_repository.set_access_profile(
            employee_code,
            team_id=f"TEAM-{factory_id}",
            team_name=f"{factory_name}生产组",
            position=bamboo_role,
            roles=workspace_roles or ["WORKER"],
            allowed_form_types=[],
            allowed_processes=["BAMBOO_PROCESS"],
            factory_id=factory_id,
            factory_name=factory_name,
            bamboo_role=bamboo_role,
        )

    def mobile(self, employee_code: str) -> RecordedClient:
        client = TestClient(create_app(self.services))
        raw = RecordedClient(client, employee_code, "MOBILE")
        with self.recorder.step(
            f"login-mobile-{employee_code}",
            "登录移动端",
            employee_code,
            "MOBILE",
        ) as step:
            raw.post(
                step,
                "/api/v1/mobile/auth/login",
                expected_status=200,
                json={
                    "employee_code": employee_code,
                    "pin": PIN,
                    "device_id": f"{employee_code}-acceptance-phone",
                },
            )
        return raw

    def web(self, employee_code: str) -> RecordedClient:
        client = TestClient(create_app(self.services))
        raw = RecordedClient(client, employee_code, "WEB")
        with self.recorder.step(
            f"login-web-{employee_code}",
            "登录 Web 工作区",
            employee_code,
            "WEB",
        ) as step:
            raw.post(
                step,
                "/api/v1/web/auth/login",
                expected_status=200,
                json={
                    "employee_code": employee_code,
                    "pin": PIN,
                    "device_id": f"{employee_code}-acceptance-browser",
                },
            )
        return raw

    @staticmethod
    def mobile_headers(client: RecordedClient, key: str) -> dict[str, str]:
        return {
            "X-CSRF-Token": client.client.cookies["mobile_csrf"],
            "Idempotency-Key": key,
        }

    @staticmethod
    def web_headers(client: RecordedClient, key: str) -> dict[str, str]:
        return {
            "X-CSRF-Token": client.client.cookies["web_csrf"],
            "Idempotency-Key": key,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture()
def acceptance_env(
    tmp_path: Path, request: pytest.FixtureRequest
) -> Iterator[AcceptanceEnvironment]:
    run_id = os.environ.get("ACCEPTANCE_RUN_ID", "local")
    artifact_root = Path(
        os.environ.get(
            "ACCEPTANCE_ARTIFACT_DIR",
            str(_repo_root() / "artifacts" / "acceptance" / run_id),
        )
    )
    scenario_dir = artifact_root / "scenarios" / request.node.name
    recorder = ScenarioRecorder(request.node.name, scenario_dir, _repo_root())
    services = build_services(
        Settings(
            data_root=tmp_path,
            environment="test",
            bamboo_plant_audit_wait_hours=0,
        )
    )
    environment = AcceptanceEnvironment(services=services, recorder=recorder)
    request.node._acceptance_recorder = recorder
    request.node._acceptance_services = services
    try:
        yield environment
    finally:
        snapshot_database(
            services.engine,
            scenario_dir / "database-snapshot.json",
            known_ids=recorder.known_ids,
        )
        recorder.finalize()
        services.engine.dispose()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed or call.excinfo is None:
        return
    recorder = getattr(item, "_acceptance_recorder", None)
    if recorder is None:
        return
    current = recorder.current_step
    if current is None:
        recorder.record_outside_step_failure(call.excinfo.value)
