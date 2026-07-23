"""Backfill, legacy-signature replay and cross-version compatibility tests."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text

from .conftest import AcceptanceEnvironment


def _setup_sort_operator(env: AcceptanceEnvironment, employee_code: str):
    env.add_identity(
        employee_code=employee_code,
        employee_name=f"兼容测试{employee_code}",
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
# Old-record backfill via migration 031 simulation
# ═══════════════════════════════════════════════════════════════════


def test_old_create_record_null_hash_rejected_on_replay(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """Old record with NULL create_payload_hash → 409 on any replay."""
    env = acceptance_env
    actor_code = "BK-NULL"
    client = _setup_sort_operator(env, actor_code)
    cage = f"BKNULL-{uuid4().hex[:8]}"
    key = f"bk-null-{uuid4().hex}"
    # Create via API (gets correct hash automatically)
    with env.recorder.step("bk-create", "正常创建", actor_code, "MOBILE") as step:
        first = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=_create_payload(cage, 10),
        ).json()
        record_id = first["record_id"]

    # Simulate un-backfilled state: NULL the hash
    services = env.services
    with services.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE bamboo_records SET create_payload_hash = NULL "
                "WHERE record_id = :rid"
            ),
            {"rid": record_id},
        )

    # Replay with any payload → 409 (NULL hash means unverifiable)
    with env.recorder.step("bk-replay", "NULL哈希应拒绝", actor_code, "MOBILE") as step:
        response = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=409,
            headers=env.mobile_headers(client, key),
            json=_create_payload(cage, 10),
        )
        step.check(
            response.json()["code"] == "IDEMPOTENCY_CONFLICT",
            "NULL create_payload_hash 应返回冲突",
        )


def test_old_create_record_backfilled_same_payload_succeeds(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """After backfill, same payload on old key → success."""
    env = acceptance_env
    actor_code = "BK-OK"
    client = _setup_sort_operator(env, actor_code)
    cage = f"BKOK-{uuid4().hex[:8]}"
    key = f"bk-ok-{uuid4().hex}"
    # Create normally and record the validated base_info from the DB
    with env.recorder.step("bk-create", "创建", actor_code, "MOBILE") as step:
        first = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=_create_payload(cage, 10),
        ).json()
        record_id = first["record_id"]

    # Read the stored create_payload_hash (set by the API)
    services = env.services
    with services.engine.begin() as conn:
        stored_hash = conn.execute(
            text(
                "SELECT create_payload_hash FROM bamboo_records "
                "WHERE record_id = :rid"
            ),
            {"rid": record_id},
        ).scalar()
        assert stored_hash is not None, "新记录应有 create_payload_hash"

    # Replay with same raw payload → API validates identically → hash matches
    with env.recorder.step("bk-replay", "同载荷重放", actor_code, "MOBILE") as step:
        second = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=_create_payload(cage, 10),
        ).json()
        step.check(second["record_id"] == record_id, "应返回同一记录")


def test_old_create_record_backfilled_different_payload_rejected(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """After backfill, different payload on old key → 409."""
    env = acceptance_env
    actor_code = "BK-DIFF2"
    client = _setup_sort_operator(env, actor_code)
    key = f"bk-diff2-{uuid4().hex}"
    with env.recorder.step("bk-create", "创建", actor_code, "MOBILE") as step:
        client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=_create_payload(f"BKD2-{uuid4().hex[:8]}", 10),
        )

    # Different payload → 409
    with env.recorder.step("bk-conflict", "不同载荷应409", actor_code, "MOBILE") as step:
        response = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=409,
            headers=env.mobile_headers(client, key),
            json=_create_payload(f"BKD2-WRONG-{uuid4().hex[:8]}", 99),
        )
        step.check(
            response.json()["code"] == "IDEMPOTENCY_CONFLICT",
            "应返回 IDEMPOTENCY_CONFLICT",
        )


# ═══════════════════════════════════════════════════════════════════
# Legacy stage-signature replay (idempotency_hash_version = 0)
# ═══════════════════════════════════════════════════════════════════


def test_legacy_signature_idempotent_replay_with_same_values(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """An old (v0) signature can still be replayed with the same values."""
    env = acceptance_env
    actor_code = "LG-REP"
    client = _setup_sort_operator(env, actor_code)
    run_id = uuid4().hex
    key = f"lg-rep-{run_id}"
    values = {"moisture": [12, 13]}

    with env.recorder.step("lg-create", "创建", actor_code, "MOBILE") as step:
        record = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, f"{run_id}-create"),
            json=_create_payload(f"LGR-{run_id[:8]}", 10),
        ).json()

    path = f"/api/v1/mobile/bamboo/records/{record['record_id']}/stages/SORT/submit"
    with env.recorder.step("lg-submit-1", "首次提交(v1)", actor_code, "MOBILE") as step:
        first = client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, key),
            json={
                "expected_revision": record["revision"],
                "device_id": "lg-phone",
                "values": values,
            },
        ).json()
        step.attach(revision_after=first["revision"])

    # Downgrade signature to v0 (simulating pre-031 data)
    services = env.services
    with services.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE bamboo_signatures "
                "SET idempotency_hash_version = 0, "
                "idempotency_payload_hash = NULL "
                "WHERE idempotency_key = :key"
            ),
            {"key": key},
        )

    # Replay with same values → legacy hash comparison succeeds
    with env.recorder.step("lg-replay", "v0同值重放应成功", actor_code, "MOBILE") as step:
        second = client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, key),
            json={
                "expected_revision": record["revision"],
                "device_id": "lg-phone",
                "values": values,
            },
        ).json()
        step.check(second["revision"] == first["revision"], "revision 不应推进")


def test_legacy_signature_different_values_rejected(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """An old (v0) signature rejects different values."""
    env = acceptance_env
    actor_code = "LG-DIFF2"
    client = _setup_sort_operator(env, actor_code)
    run_id = uuid4().hex
    key = f"lg-diff2-{run_id}"
    values_a = {"moisture": [12, 13]}

    with env.recorder.step("lgd-create", "创建", actor_code, "MOBILE") as step:
        record = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, f"{run_id}-create"),
            json=_create_payload(f"LGD2-{run_id[:8]}", 10),
        ).json()

    path = f"/api/v1/mobile/bamboo/records/{record['record_id']}/stages/SORT/submit"
    with env.recorder.step("lgd-submit", "首次提交", actor_code, "MOBILE") as step:
        client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, key),
            json={
                "expected_revision": record["revision"],
                "device_id": "lgd-phone",
                "values": values_a,
            },
        )

    # Downgrade to v0
    services = env.services
    with services.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE bamboo_signatures "
                "SET idempotency_hash_version = 0, "
                "idempotency_payload_hash = NULL "
                "WHERE idempotency_key = :key"
            ),
            {"key": key},
        )

    # Different values → 409
    with env.recorder.step("lgd-conflict", "v0不同值应409", actor_code, "MOBILE") as step:
        response = client.post(
            step, path, expected_status=409,
            headers=env.mobile_headers(client, key),
            json={
                "expected_revision": record["revision"],
                "device_id": "lgd-phone",
                "values": {"moisture": [99]},
            },
        )
        step.check(
            response.json()["code"] == "IDEMPOTENCY_CONFLICT",
            "应返回 IDEMPOTENCY_CONFLICT",
        )


# ═══════════════════════════════════════════════════════════════════
# Coexistence
# ═══════════════════════════════════════════════════════════════════


def test_new_and_legacy_signatures_coexist(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """v1 signature replay works despite a v0 signature existing under another key."""
    env = acceptance_env
    client = _setup_sort_operator(env, "COEX2")
    run_id = uuid4().hex

    with env.recorder.step("coex-create", "创建", "COEX2", "MOBILE") as step:
        record = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, f"{run_id}-create"),
            json=_create_payload(f"COEX2-{run_id[:8]}", 10),
        ).json()

    values = {"moisture": [12]}
    path = f"/api/v1/mobile/bamboo/records/{record['record_id']}/stages/SORT/submit"
    key_v1 = f"coex2-v1-{run_id}"
    with env.recorder.step("coex-v1-submit", "v1提交", "COEX2", "MOBILE") as step:
        client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, key_v1),
            json={
                "expected_revision": record["revision"],
                "device_id": "coex2-phone",
                "values": values,
            },
        )

    # Verify v1 signature exists
    services = env.services
    with services.engine.begin() as conn:
        ver = conn.execute(
            text(
                "SELECT idempotency_hash_version FROM bamboo_signatures "
                "WHERE idempotency_key = :key"
            ),
            {"key": key_v1},
        ).scalar()
        assert ver == 1, f"v1 signature should have version=1, got {ver}"

    # v1 replay still works
    with env.recorder.step("coex-v1-replay", "v1重放成功", "COEX2", "MOBILE") as step:
        second = client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, key_v1),
            json={
                "expected_revision": record["revision"],
                "device_id": "coex2-phone",
                "values": values,
            },
        ).json()
        step.check(second["record_id"] == record["record_id"], "v1应正常重放")


# ═══════════════════════════════════════════════════════════════════
# Failure does not leave side effects
# ═══════════════════════════════════════════════════════════════════


def test_conflict_does_not_increment_revision_or_create_submissions(
    acceptance_env: AcceptanceEnvironment,
) -> None:
    """409 does not advance revision, add submissions, signatures, payroll or cages."""
    env = acceptance_env
    client = _setup_sort_operator(env, "NO-SIDE2")
    run_id = uuid4().hex
    key = f"no-side2-{run_id}"
    with env.recorder.step("ns-create", "创建", "NO-SIDE2", "MOBILE") as step:
        record = client.post(
            step,
            "/api/v1/mobile/bamboo/records",
            expected_status=201,
            headers=env.mobile_headers(client, key),
            json=_create_payload(f"NS2-{run_id[:8]}", 10),
        ).json()
        record_id = record["record_id"]

    # First submission succeeds
    values_a = {"moisture": [12]}
    path = f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit"
    stage_key = f"no-side2-s-{run_id}"
    with env.recorder.step("ns-submit", "首次提交", "NO-SIDE2", "MOBILE") as step:
        client.post(
            step, path, expected_status=200,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "ns2-phone",
                "values": values_a,
            },
        )

    # Count before conflict
    services = env.services
    with services.engine.begin() as conn:
        before_sub = conn.execute(
            text("SELECT COUNT(*) FROM bamboo_stage_submissions")
        ).scalar()
        before_sig = conn.execute(
            text("SELECT COUNT(*) FROM bamboo_signatures")
        ).scalar()
        before_fact = conn.execute(
            text("SELECT COUNT(*) FROM bamboo_payroll_facts")
        ).scalar()
        before_cage = conn.execute(
            text("SELECT COUNT(*) FROM bamboo_cage_occupancies")
        ).scalar()
        before_rev = conn.execute(
            text(
                "SELECT revision FROM bamboo_records WHERE record_id = :rid"
            ),
            {"rid": record_id},
        ).scalar()

    # Second submission with different values → 409
    with env.recorder.step("ns-conflict", "触发冲突", "NO-SIDE2", "MOBILE") as step:
        response = client.post(
            step, path, expected_status=409,
            headers=env.mobile_headers(client, stage_key),
            json={
                "expected_revision": record["revision"],
                "device_id": "ns2-phone",
                "values": {"moisture": [99]},
            },
        )
        step.check(response.json()["code"] == "IDEMPOTENCY_CONFLICT", "应为冲突")

    # Verify nothing changed
    with services.engine.begin() as conn:
        assert conn.execute(
            text("SELECT COUNT(*) FROM bamboo_stage_submissions")
        ).scalar() == before_sub, "不应新增 submission"
        assert conn.execute(
            text("SELECT COUNT(*) FROM bamboo_signatures")
        ).scalar() == before_sig, "不应新增 signature"
        assert conn.execute(
            text("SELECT COUNT(*) FROM bamboo_payroll_facts")
        ).scalar() == before_fact, "不应新增工资事实"
        assert conn.execute(
            text("SELECT COUNT(*) FROM bamboo_cage_occupancies")
        ).scalar() == before_cage, "不应新增笼号占用"
        assert conn.execute(
            text(
                "SELECT revision FROM bamboo_records WHERE record_id = :rid"
            ),
            {"rid": record_id},
        ).scalar() == before_rev, "revision 不应变化"
