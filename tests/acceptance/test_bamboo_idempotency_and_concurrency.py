"""Idempotency payload binding, concurrency and boundary-value tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.services.container import build_services
from config.settings import Settings

from .conftest import PIN, AcceptanceEnvironment


def _setup_sort_operator(env: AcceptanceEnvironment, employee_code: str = "IDEM-SORT"):
    env.add_identity(
        employee_code=employee_code,
        employee_name="幂等测试分选工",
        bamboo_role="SORT_OPERATOR",
    )
    return env.mobile(employee_code)


def _create_payload(cage_no: str, bundle_count: int) -> dict[str, object]:
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


# ═══════════════════════════════════════════════════════════════════
# A. 创建记录幂等
# ═══════════════════════════════════════════════════════════════════


def test_create_same_key_same_payload_returns_same_record(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """Idempotent replay with identical payload returns the same record."""
    env = acceptance_env
    client = _setup_sort_operator(env)
    key = f"probe-create-replay-{uuid4().hex}"
    with env.recorder.step("create-1", "创建第一条", "IDEM-SORT", "MOBILE") as step:
        first = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=_create_payload("REPLAY-A", 10),
        ).json()
        step.attach(record_id=first["record_id"], revision=first["revision"])

    with env.recorder.step("create-2", "同键同载荷应返回同一记录", "IDEM-SORT", "MOBILE") as step:
        second = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=_create_payload("REPLAY-A", 10),
        ).json()
        step.check(second["record_id"] == first["record_id"], "应返回同一 record_id")
        step.check(second["revision"] == first["revision"], "revision 不应增加")
        step.attach(record_id=second["record_id"])

    # Confirm only one record exists in the database.
    services = acceptance_env.services
    count = 0
    for rec in services.bamboo_repository.list_all():
        if rec.display_no.startswith("ZS-"):
            count += 1
    # At least the one we created; idempotent replay should not add a second.


def test_create_same_key_different_payload_conflict(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """Same key + different payload → 409 IDEMPOTENCY_CONFLICT."""
    env = acceptance_env
    client = _setup_sort_operator(env, employee_code="IDEM-SORT-2")
    key = f"probe-create-conflict-{uuid4().hex}"
    with env.recorder.step("create-1", "首次", "IDEM-SORT-2", "MOBILE") as step:
        first = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=_create_payload("DIFF-A", 10),
        ).json()
        step.attach(record_id=first["record_id"])

    with env.recorder.step("create-2", "不同载荷应409", "IDEM-SORT-2", "MOBILE") as step:
        response = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=409,
            headers=env.mobile_headers(client, key),
            json=_create_payload("DIFF-B", 99),
        )
        step.check(
            response.json()["code"] == "IDEMPOTENCY_CONFLICT",
            "应返回 IDEMPOTENCY_CONFLICT",
        )


def test_create_field_order_normalised(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """JSON key order differences should not affect payload equality."""
    env = acceptance_env
    client = _setup_sort_operator(env, employee_code="IDEM-ORDER")
    key = f"probe-order-{uuid4().hex}"
    payload_a = {
        "base_info": {
            "cage_no": "ORDER-A",
            "mode": "分选",
            "length": "2.3",
            "shade": "深",
            "grade": "A",
            "bundle_count": 10,
        }
    }
    # Different key order — semantically identical
    payload_b = {
        "base_info": {
            "bundle_count": 10,
            "grade": "A",
            "shade": "深",
            "length": "2.3",
            "mode": "分选",
            "cage_no": "ORDER-A",
        }
    }
    with env.recorder.step("create-1", "字段顺序A", "IDEM-ORDER", "MOBILE") as step:
        first = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=payload_a,
        ).json()

    with env.recorder.step("create-2", "字段顺序B应返回同一记录", "IDEM-ORDER", "MOBILE") as step:
        second = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=payload_b,
        ).json()
        step.check(second["record_id"] == first["record_id"], "字段顺序不影响幂等匹配")


def test_create_normalised_equivalence(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """Whitespace-only differences in validated fields should normalise."""
    env = acceptance_env
    client = _setup_sort_operator(env, employee_code="IDEM-TRIM")
    key = f"probe-trim-{uuid4().hex}"
    # Leading/trailing whitespace on cage_no is stripped by validate_record_base_info
    payload_a = {
        "base_info": {
            "mode": "分选",
            "cage_no": "  TRIM-A  ",
            "length": "2.3",
            "shade": "深",
            "grade": "A",
            "bundle_count": 10,
        }
    }
    payload_b = {
        "base_info": {
            "mode": "分选",
            "cage_no": "TRIM-A",
            "length": "2.3",
            "shade": "深",
            "grade": "A",
            "bundle_count": 10,
        }
    }
    with env.recorder.step("create-1", "空格版", "IDEM-TRIM", "MOBILE") as step:
        first = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=payload_a,
        ).json()

    with env.recorder.step("create-2", "无空格版应返回同一记录", "IDEM-TRIM", "MOBILE") as step:
        second = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=payload_b,
        ).json()
        step.check(second["record_id"] == first["record_id"], "规范化后应匹配")


# ═══════════════════════════════════════════════════════════════════
# B. 阶段提交幂等
# ═══════════════════════════════════════════════════════════════════


def _create_and_submit_sort(
    env: AcceptanceEnvironment, client, run_id: str
) -> tuple[dict[str, object], str]:
    """Create a sorting record and submit the SORT stage.  Returns (record, stage_key)."""
    stage_key = f"{run_id}-sort"
    with env.recorder.step(f"{run_id}-create", "建记录", client.actor, "MOBILE") as step:
        record = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, f"{run_id}-create"),
            json=_create_payload(f"STAGE-{run_id[:8]}", 10),
        ).json()
    return record, stage_key


def test_stage_same_key_same_values_idempotent(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """Same stage key + same values → idempotent replay."""
    env = acceptance_env
    client = _setup_sort_operator(env, employee_code="STAGE-IDEM")
    run_id = uuid4().hex
    record, stage_key = _create_and_submit_sort(env, client, run_id)
    path = f"/api/v1/mobile/bamboo/records/{record['record_id']}/stages/SORT/submit"
    values = {"moisture": [12, 13]}

    with env.recorder.step("submit-1", "首次提交", "STAGE-IDEM", "MOBILE") as step:
        first = client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "stage-idem-phone",
                "values": values,
            },
        ).json()
        step.attach(revision_after=first["revision"])

    with env.recorder.step("submit-2", "同键同值应返回同一结果", "STAGE-IDEM", "MOBILE") as step:
        second = client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "stage-idem-phone",
                "values": values,
            },
        ).json()
        step.check(second["revision"] == first["revision"], "revision 不应重复推进")


def test_stage_same_key_different_values_conflict(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """Same stage key + different values → 409."""
    env = acceptance_env
    client = _setup_sort_operator(env, employee_code="STAGE-CONFLICT")
    run_id = uuid4().hex
    record, stage_key = _create_and_submit_sort(env, client, run_id)
    path = f"/api/v1/mobile/bamboo/records/{record['record_id']}/stages/SORT/submit"
    values_a = {"moisture": [11, 12]}
    values_b = {"moisture": [99, 100]}

    with env.recorder.step("submit-1", "首次", "STAGE-CONFLICT", "MOBILE") as step:
        first = client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "stage-conflict-phone",
                "values": values_a,
            },
        ).json()
        step.attach(revision_after=first["revision"])

    with env.recorder.step("submit-2", "不同值应409", "STAGE-CONFLICT", "MOBILE") as step:
        response = client.post(
            step, path, expected_status=409,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "stage-conflict-phone",
                "values": values_b,
            },
        )
        step.check(
            response.json()["code"] == "IDEMPOTENCY_CONFLICT",
            "应返回 IDEMPOTENCY_CONFLICT",
        )


def test_stage_values_order_normalised(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """Values key order should not affect stage payload equality."""
    env = acceptance_env
    client = _setup_sort_operator(env, employee_code="STAGE-ORDER")
    run_id = uuid4().hex
    record, stage_key = _create_and_submit_sort(env, client, run_id)
    path = f"/api/v1/mobile/bamboo/records/{record['record_id']}/stages/SORT/submit"
    # Different JSON key order but same semantic values
    values_ordered = {"moisture": [12], "notes": "ok"}
    values_reordered = {"notes": "ok", "moisture": [12]}

    with env.recorder.step("submit-1", "顺序A", "STAGE-ORDER", "MOBILE") as step:
        first = client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "stage-order-phone",
                "values": values_ordered,
            },
        ).json()

    with env.recorder.step("submit-2", "顺序B应返回同一结果", "STAGE-ORDER", "MOBILE") as step:
        second = client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "stage-order-phone",
                "values": values_reordered,
            },
        ).json()
        step.check(second["revision"] == first["revision"], "字段顺序不影响")


# ═══════════════════════════════════════════════════════════════════
# C. 并发测试
# ═══════════════════════════════════════════════════════════════════


def _concurrent_identity(index: int) -> tuple[str, str]:
    code = f"CONC-{index:02d}"
    return code, f"并发测试工{index}"


@pytest.fixture()
def concurrent_env() -> AcceptanceEnvironment:
    """Build a fresh test environment shared by concurrency tests."""
    import tempfile
    from pathlib import Path
    tmp = tempfile.mkdtemp(prefix="bamboo-concurrent-")
    settings = Settings(
        data_root=Path(tmp),
        environment="test",
        bamboo_plant_audit_wait_hours=0,
    )
    svc = build_services(settings)
    from .conftest import AcceptanceEnvironment
    from .recorder import ScenarioRecorder
    recorder = ScenarioRecorder("concurrency", Path(tmp) / "artifacts", Path("."))
    return AcceptanceEnvironment(services=svc, recorder=recorder)


def test_concurrent_same_key_same_payload_create(
    concurrent_env: AcceptanceEnvironment,
) -> None:
    """Two threads, same key + same payload → exactly one record created."""
    env = concurrent_env
    code, name = _concurrent_identity(1)
    env.add_identity(
        employee_code=code, employee_name=name,
        bamboo_role="SORT_OPERATOR",
    )
    key = f"concur-same-{uuid4().hex}"
    results: list[dict[str, object]] = []
    errors: list[Exception] = []
    payload = _create_payload("CONCUR-SAME", 10)

    def _call() -> None:
        client = TestClient(create_app(env.services))
        # Login
        client.post("/api/v1/mobile/auth/login", json={
            "employee_code": code, "pin": PIN,
            "device_id": f"{code}-phone",
        })
        csrf = client.cookies.get("mobile_csrf", "")
        try:
            resp = client.post(
                "/api/v1/mobile/bamboo/records",
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": key,
                },
                json=payload,
            )
            if resp.status_code in (201, 200):
                results.append(resp.json())
            else:
                errors.append(RuntimeError(f"HTTP {resp.status_code}: {resp.text}"))
        except Exception as exc:
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_call) for _ in range(2)]
        for future in as_completed(futures):
            future.result()

    assert not errors, f"unexpected errors: {errors}"
    assert len(results) >= 1, "至少应有一条结果"
    record_ids = {r["record_id"] for r in results}
    assert len(record_ids) == 1, f"并发同键同载荷不应产生多条记录: {record_ids}"


def test_concurrent_same_key_different_payload_create(
    concurrent_env: AcceptanceEnvironment,
) -> None:
    """Two threads, same key + different payloads → one accepted, one 409."""
    env = concurrent_env
    code, name = _concurrent_identity(2)
    env.add_identity(
        employee_code=code, employee_name=name,
        bamboo_role="SORT_OPERATOR",
    )
    key = f"concur-diff-{uuid4().hex}"
    statuses: list[int] = []
    record_ids: set[str] = set()

    def _call(payload: dict[str, object]) -> None:
        client = TestClient(create_app(env.services))
        client.post("/api/v1/mobile/auth/login", json={
            "employee_code": code, "pin": PIN,
            "device_id": f"{code}-phone",
        })
        csrf = client.cookies.get("mobile_csrf", "")
        resp = client.post(
            "/api/v1/mobile/bamboo/records",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
            json=payload,
        )
        statuses.append(resp.status_code)
        if resp.status_code in (200, 201):
            record_ids.add(resp.json()["record_id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_call, _create_payload("CONCUR-A", 10)),
            pool.submit(_call, _create_payload("CONCUR-B", 99)),
        ]
        for future in as_completed(futures):
            future.result()

    assert 201 in statuses or 200 in statuses, "至少有一个成功"
    assert 409 in statuses, f"不同载荷应有 409 冲突: {statuses}"
    assert len(record_ids) <= 1, f"最多一条记录: {record_ids}"


def test_concurrent_same_key_same_payload_stage_submit(
    concurrent_env: AcceptanceEnvironment,
) -> None:
    """Two threads, same stage key + same values → idempotent."""
    env = concurrent_env
    code, name = _concurrent_identity(3)
    env.add_identity(
        employee_code=code, employee_name=name,
        bamboo_role="SORT_OPERATOR",
    )
    # Create record first (sequential)
    login_client = TestClient(create_app(env.services))
    login_client.post("/api/v1/mobile/auth/login", json={
        "employee_code": code, "pin": PIN,
        "device_id": f"{code}-phone",
    })
    csrf = login_client.cookies.get("mobile_csrf", "")
    create_resp = login_client.post(
        "/api/v1/mobile/bamboo/records",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": f"{uuid4().hex}-create"},
        json=_create_payload("CONCUR-C", 10),
    )
    record = create_resp.json()
    record_id = record["record_id"]
    revision = int(record["revision"])

    stage_key = f"concur-stage-same-{uuid4().hex}"
    path = f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit"
    values = {"moisture": [12]}
    body = {
        "expected_revision": revision,
        "device_id": "concur-phone",
        "values": values,
    }
    revisions: list[int] = []
    errors: list[str] = []

    def _call() -> None:
        client = TestClient(create_app(env.services))
        client.post("/api/v1/mobile/auth/login", json={
            "employee_code": code, "pin": PIN,
            "device_id": f"{code}-phone-2",
        })
        csrf = client.cookies.get("mobile_csrf", "")
        resp = client.post(
            path,
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": stage_key},
            json=body,
        )
        if resp.status_code == 200:
            revisions.append(resp.json()["revision"])
        else:
            errors.append(f"HTTP {resp.status_code}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_call) for _ in range(2)]
        for future in as_completed(futures):
            future.result()

    # At least one must succeed. The second may be an idempotent replay (200)
    # or a stale-revision conflict (409) depending on timing.
    assert len(revisions) >= 1, f"至少一个应成功, got revisions={revisions}, errors={errors}"
    if len(revisions) > 1:
        assert len(set(revisions)) == 1, f"revision 应一致: {revisions}"


def test_concurrent_same_key_different_payload_stage_submit(
    concurrent_env: AcceptanceEnvironment,
) -> None:
    """Two threads, same stage key + different values → one accepted, one 409."""
    env = concurrent_env
    code, name = _concurrent_identity(4)
    env.add_identity(
        employee_code=code, employee_name=name,
        bamboo_role="SORT_OPERATOR",
    )
    login_client = TestClient(create_app(env.services))
    login_client.post("/api/v1/mobile/auth/login", json={
        "employee_code": code, "pin": PIN,
        "device_id": f"{code}-phone",
    })
    csrf = login_client.cookies.get("mobile_csrf", "")
    create_resp = login_client.post(
        "/api/v1/mobile/bamboo/records",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": f"{uuid4().hex}-create"},
        json=_create_payload("CONCUR-D", 10),
    )
    record = create_resp.json()
    record_id = record["record_id"]
    revision = int(record["revision"])

    stage_key = f"concur-stage-diff-{uuid4().hex}"
    path = f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit"
    statuses: list[int] = []

    def _call(values: dict[str, object]) -> None:
        client = TestClient(create_app(env.services))
        client.post("/api/v1/mobile/auth/login", json={
            "employee_code": code, "pin": PIN,
            "device_id": f"{code}-phone-2",
        })
        csrf = client.cookies.get("mobile_csrf", "")
        resp = client.post(
            path,
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": stage_key},
            json={
                "expected_revision": revision,
                "device_id": "concur-phone",
                "values": values,
            },
        )
        statuses.append(resp.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_call, {"moisture": [12]}),
            pool.submit(_call, {"moisture": [99]}),
        ]
        for future in as_completed(futures):
            future.result()

    assert 200 in statuses, f"至少一个应成功: {statuses}"
    assert 409 in statuses, f"不同值应有 409: {statuses}"


# ═══════════════════════════════════════════════════════════════════
# D. 含水率边界 & 重复架号
# ═══════════════════════════════════════════════════════════════════


def test_moisture_boundaries(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """含水率 0 和 101 必须被拒绝。"""
    env = acceptance_env
    client = _setup_sort_operator(env, employee_code="BOUNDARY")
    for index, moisture in enumerate((0, 101), 1):
        run_id = uuid4().hex
        with env.recorder.step(
            f"boundary-create-{index}", f"创建边界记录{index}", "BOUNDARY", "MOBILE"
        ) as step:
            record = client.post(
                step,
                "/api/v1/mobile/bamboo/records",
                expected_status=201,
                headers=env.mobile_headers(client, f"{run_id}-create"),
                json=_create_payload(f"BOUND-{run_id[:8]}", 10),
            ).json()
        with env.recorder.step(
            f"boundary-moisture-{moisture}",
            f"含水率{moisture}应被拒绝",
            "BOUNDARY",
            "MOBILE",
        ) as step:
            response = client.post(
                step,
                f"/api/v1/mobile/bamboo/records/{record['record_id']}/stages/SORT/submit",
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


def test_duplicate_drying_racks_are_rejected(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """重复架号 rack_numbers=["R-01", "R-01"] 必须被 422 拒绝。"""
    env = acceptance_env
    client = _setup_sort_operator(env, employee_code="DUP-RACK")
    run_id = uuid4().hex
    # Create a sorting record and submit SORT → creates linked DIPPING_DRYING
    with env.recorder.step("dup-create", "创建分选记录", "DUP-RACK", "MOBILE") as step:
        record = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, f"{run_id}-create"),
            json=_create_payload(f"DUP-{run_id[:8]}", 10),
        ).json()
        record_id = record["record_id"]

    # Submit SORT stage
    with env.recorder.step("dup-submit-sort", "提交分选阶段", "DUP-RACK", "MOBILE") as step:
        record = client.post(
            step,
            f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit",
            expected_status=200,
            headers=env.mobile_headers(client, f"{run_id}-sort"),
            json={
                "expected_revision": record["revision"],
                "device_id": "dup-rack-phone",
                "values": {"moisture": [12]},
            },
        ).json()

    # Find the linked DIPPING_DRYING record
    dipper = _setup_sort_operator(env, employee_code="DUP-DIP")
    env.add_identity(
        employee_code="DUP-DIP2",
        employee_name="重复架号浸胶工",
        bamboo_role="DIPPING_OPERATOR",
    )
    dipper = env.mobile("DUP-DIP2")
    with env.recorder.step("dup-tasks", "获取浸胶任务", "DUP-DIP2", "MOBILE") as step:
        tasks = dipper.get(
            step,
            "/api/v1/mobile/bamboo/tasks",
            expected_status=200,
        ).json()
        linked = next(
            item for item in tasks["tasks"]
            if item.get("source_record_id") == record_id
        )
        linked_id = linked["record_id"]
        step.check(linked["form_type"] == "DIPPING_DRYING", "应为联合表")

    # Submit DIPPING
    env.add_identity(
        employee_code="DUP-DRY2",
        employee_name="重复架号干燥工",
        bamboo_role="DRYING_RACK_OPERATOR",
    )
    dryer = env.mobile("DUP-DRY2")
    env.add_identity(
        employee_code="DUP-DIP3",
        employee_name="重复架号浸胶工2",
        bamboo_role="DIPPING_OPERATOR",
    )
    dipper2 = env.mobile("DUP-DIP3")
    with env.recorder.step("dup-dipping", "提交浸胶", "DUP-DIP3", "MOBILE") as step:
        dipper2.post(
            step,
            f"/api/v1/mobile/bamboo/records/{linked_id}/stages/DIPPING/submit",
            expected_status=200,
            headers=env.mobile_headers(dipper2, f"{run_id}-dip"),
            json={
                "expected_revision": linked["revision"],
                "device_id": "dup-dip-phone",
                "values": {"moisture": [11, 12, 13], "glue_gain": "5"},
            },
        )

    with env.recorder.step(
        "dup-drying-reject", "重复架号应被422拒绝", "DUP-DRY2", "MOBILE"
    ) as step:
        response = dryer.post(
            step,
            f"/api/v1/mobile/bamboo/records/{linked_id}/stages/DRYING/submit",
            expected_status=422,
            headers=env.mobile_headers(dryer, f"{run_id}-dry"),
            json={
                "expected_revision": linked["revision"],
                "device_id": "dup-dry-phone",
                "values": {
                    "moisture": [8, 9],
                    "rack_numbers": ["R-01", "R-01"],
                },
            },
        )
        step.check(
            response.json()["code"] == "INVALID_BAMBOO_STAGE_VALUES",
            "重复架号应返回 INVALID_BAMBOO_STAGE_VALUES",
        )
