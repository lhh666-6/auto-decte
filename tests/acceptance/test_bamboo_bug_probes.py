"""Focused probes that intentionally expose likely consistency defects."""

from __future__ import annotations

from uuid import uuid4

from .conftest import AcceptanceEnvironment


def _setup_sort_operator(env: AcceptanceEnvironment):
    env.add_identity(
        employee_code="PROBE-SORT",
        employee_name="幂等探针分选工",
        bamboo_role="SORT_OPERATOR",
    )
    return env.mobile("PROBE-SORT")


def _payload(cage_no: str, bundle_count: int) -> dict[str, object]:
    return {
        "base_info": {
            "mode": "分选",
            "cage_no": cage_no,
            "length": "2.3",
            "shade": "深",
            "grade": "A",
            "bundle_count": bundle_count,
        }
    }


def test_create_idempotency_key_rejects_different_payload(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """Same key + different payload must not silently return the old record."""
    env = acceptance_env
    client = _setup_sort_operator(env)
    key = f"probe-create-{uuid4().hex}"
    with env.recorder.step(
        "probe-create-first",
        "首次创建记录",
        "PROBE-SORT",
        "MOBILE",
    ) as step:
        first = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=_payload("PROBE-A", 10),
        ).json()
        step.attach(record_id=first["record_id"])

    with env.recorder.step(
        "probe-create-mismatch",
        "相同幂等键配不同创建载荷应冲突",
        "PROBE-SORT",
        "MOBILE",
    ) as step:
        response = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=409,
            headers=env.mobile_headers(client, key),
            json=_payload("PROBE-B", 99),
        )
        step.check(
            response.json()["code"] == "IDEMPOTENCY_CONFLICT",
            "不同载荷复用创建幂等键应返回 IDEMPOTENCY_CONFLICT",
        )


def test_stage_idempotency_key_rejects_different_payload(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """A stage signature key must be bound to one canonical payload."""
    env = acceptance_env
    client = _setup_sort_operator(env)
    run_id = uuid4().hex
    with env.recorder.step(
        "probe-stage-create",
        "为阶段幂等探针创建记录",
        "PROBE-SORT",
        "MOBILE",
    ) as step:
        record = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, f"{run_id}-create"),
            json=_payload(f"STAGE-{run_id[:8]}", 10),
        ).json()
        step.attach(record_id=record["record_id"])

    stage_key = f"{run_id}-sort"
    path = (
        f"/api/v1/mobile/bamboo/records/{record['record_id']}"
        "/stages/SORT/submit"
    )
    with env.recorder.step(
        "probe-stage-first",
        "首次提交分选阶段",
        "PROBE-SORT",
        "MOBILE",
    ) as step:
        client.post(
            step,
            path,
            expected_status=200,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "probe-phone",
                "values": {"moisture": [12]},
            },
        )

    with env.recorder.step(
        "probe-stage-mismatch",
        "相同阶段幂等键配不同载荷应冲突",
        "PROBE-SORT",
        "MOBILE",
    ) as step:
        response = client.post(
            step,
            path,
            expected_status=409,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "probe-phone",
                "values": {"moisture": [99]},
            },
        )
        step.check(
            response.json()["code"] == "IDEMPOTENCY_CONFLICT",
            "不同阶段载荷复用幂等键应返回 IDEMPOTENCY_CONFLICT",
        )


def test_moisture_boundaries(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    env = acceptance_env
    client = _setup_sort_operator(env)
    for index, moisture in enumerate((0, 101), 1):
        run_id = uuid4().hex
        with env.recorder.step(
            f"boundary-create-{index}",
            "创建边界值记录",
            "PROBE-SORT",
            "MOBILE",
        ) as step:
            record = client.post(
                step,
                "/api/v1/mobile/bamboo/records",
                expected_status=201,
                headers=env.mobile_headers(client, f"{run_id}-create"),
                json=_payload(f"BOUND-{run_id[:8]}", 10),
            ).json()
        with env.recorder.step(
            f"boundary-moisture-{moisture}",
            f"含水率 {moisture} 应被拒绝",
            "PROBE-SORT",
            "MOBILE",
        ) as step:
            response = client.post(
                step,
                (
                    f"/api/v1/mobile/bamboo/records/{record['record_id']}"
                    "/stages/SORT/submit"
                ),
                expected_status=422,
                headers=env.mobile_headers(client, f"{run_id}-stage"),
                json={
                    "expected_revision": record["revision"],
                    "device_id": "boundary-phone",
                    "values": {"moisture": [moisture]},
                },
            )
            step.check(
                response.json()["code"] == "INVALID_BAMBOO_STAGE_VALUES",
                "含水率边界错误码不稳定",
            )
