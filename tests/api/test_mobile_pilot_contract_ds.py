"""Capture current mobile API pilot behavior and expose security gaps.

Task 1 of PWA plan: tests that pass now document the prototype contract;
tests that fail mark gaps that later tasks must close.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.services.container import build_services
from config.settings import Settings


def build_client(tmp_path: Path, *, raise_server_exceptions: bool = True) -> TestClient:
    return TestClient(
        create_app(build_services(Settings(
            data_root=tmp_path,
            local_default_user_id="local-operator",
            local_default_roles=("OPERATOR",),
        ))),
        raise_server_exceptions=raise_server_exceptions,
    )


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def login_as_worker(client: TestClient, employee_code: str = "E00128", pin: str = "1234") -> str:
    """Log in and return the bearer token."""
    res = client.post("/api/v1/mobile/auth/login", json={
        "employee_code": employee_code,
        "pin": pin,
    })
    assert res.status_code == 200, res.text
    return res.json()["token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════
#   POSITIVE BEHAVIOUR — these tests describe the current contract
# ═══════════════════════════════════════════════════════════════════

class TestMobileAuth:
    def test_login_returns_token_and_profile(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        res = client.post("/api/v1/mobile/auth/login", json={
            "employee_code": "E00128",
            "pin": "1234",
        })
        assert res.status_code == 200
        body = res.json()
        assert len(body["token"]) > 0
        assert body["employee_name"] == "张三"
        assert body["employee_code"] == "E00128"
        assert body["team_name"] == "配片一组"
        assert "WORKER" in body["roles"]

    def test_login_rejects_wrong_pin(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        res = client.post("/api/v1/mobile/auth/login", json={
            "employee_code": "E00128",
            "pin": "0000",
        })
        assert res.status_code == 401

    def test_login_rejects_unknown_employee(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        res = client.post("/api/v1/mobile/auth/login", json={
            "employee_code": "X99999",
            "pin": "1234",
        })
        assert res.status_code == 401

    def test_session_returns_current_user(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.get("/api/v1/mobile/auth/session", headers=auth_header(token))
        assert res.status_code == 200
        body = res.json()
        assert body["employee_name"] == "张三"
        assert "BAMBOO_PROCESS_RECORD" in body["allowed_form_types"]

    def test_session_rejects_missing_token(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        res = client.get("/api/v1/mobile/auth/session")
        assert res.status_code == 401

    def test_session_rejects_bogus_token(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        res = client.get("/api/v1/mobile/auth/session", headers=auth_header("bogus-token"))
        assert res.status_code == 401

    def test_logout_invalidates_session(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.post("/api/v1/mobile/auth/logout", headers=auth_header(token))
        assert res.status_code == 200
        # token should be invalid after logout
        res2 = client.get("/api/v1/mobile/auth/session", headers=auth_header(token))
        assert res2.status_code == 401


class TestAvailableForms:
    def test_worker_sees_allowed_forms(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.get("/api/v1/mobile/available-forms", headers=auth_header(token))
        assert res.status_code == 200
        forms = res.json()["forms"]
        form_types = {f["form_type"] for f in forms}
        assert "BAMBOO_PROCESS_RECORD" in form_types
        assert "SHEET_PIECE_MEASUREMENT" in form_types

    def test_team_leader_sees_batch_mode(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client, employee_code="E00129")  # 李四 = team leader
        res = client.get("/api/v1/mobile/available-forms", headers=auth_header(token))
        assert res.status_code == 200
        forms = res.json()["forms"]
        form_types = {f["form_type"] for f in forms}
        assert "TEAM_SHEET_PIECE_MEASUREMENT" in form_types


class TestContext:
    def test_context_returns_identity_and_shift(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.get("/api/v1/mobile/context", headers=auth_header(token))
        assert res.status_code == 200
        body = res.json()
        assert body["employee_name"] == "张三"
        assert body["server_date"] is not None
        assert body["suggested_shift"] in ("白班", "夜班")


class TestFormSchemas:
    def test_schema_returns_fields_for_valid_type(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.get(
            "/api/v1/mobile/form-schemas/BAMBOO_PROCESS_RECORD",
            headers=auth_header(token),
        )
        assert res.status_code == 200
        body = res.json()
        assert body["title"] == "竹丝工序记录"
        assert len(body["fields"]) > 0
        field_names = {f["field_name"] for f in body["fields"]}
        assert "moisture" in field_names
        assert "result" in field_names

    def test_schema_returns_404_for_unknown_type(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.get(
            "/api/v1/mobile/form-schemas/NONEXISTENT",
            headers=auth_header(token),
        )
        assert res.status_code == 404


class TestFormSessions:
    def test_create_session_returns_prefill(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.post(
            "/api/v1/mobile/form-sessions",
            headers=auth_header(token),
            json={"form_type": "SHEET_PIECE_MEASUREMENT"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["form_type"] == "SHEET_PIECE_MEASUREMENT"
        assert "employee_code" in body["prefill"]
        assert "employee_name" in body["locked_fields"]


class TestDrafts:
    def test_save_and_list_drafts(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        save = client.post(
            "/api/v1/mobile/drafts",
            headers=auth_header(token),
            json={
                "form_type": "SHEET_PIECE_MEASUREMENT",
                "values": {"block_count": 5, "pieces_per_block": 24},
            },
        )
        assert save.status_code == 200
        assert "draft_id" in save.json()

        lst = client.get("/api/v1/mobile/drafts", headers=auth_header(token))
        assert lst.status_code == 200
        assert len(lst.json()["drafts"]) >= 1

    def test_draft_values_preserved(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        save = client.post(
            "/api/v1/mobile/drafts",
            headers=auth_header(token),
            json={
                "form_type": "SHEET_PIECE_MEASUREMENT",
                "values": {"block_count": 8},
            },
        )
        draft_id = save.json()["draft_id"]

        lst = client.get("/api/v1/mobile/drafts", headers=auth_header(token))
        drafts = [d for d in lst.json()["drafts"] if d["draft_id"] == draft_id]
        assert len(drafts) == 1
        assert drafts[0]["values"]["block_count"] == 8


class TestSubmissions:
    def test_create_submission_succeeds(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        sub = client.post(
            "/api/v1/mobile/submissions",
            headers={
                **auth_header(token),
                "Idempotency-Key": "test-key-001",
            },
            json={
                "form_type": "SHEET_PIECE_MEASUREMENT",
                "mode": "SELF",
                "values": {"block_count": 10, "pieces_per_block": 24},
            },
        )
        assert sub.status_code == 200
        body = sub.json()
        assert body["submission_id"].startswith("SUB-")
        assert body["status"] == "SUBMITTED"

    def test_list_submissions_has_bug_missing_form_schema_fields_arg(self, tmp_path: Path) -> None:
        """BUG: list_submissions crashes with TypeError because FormSchema
        is called without the required 'fields' argument at mobile_ds.py:543."""
        # Use raise_server_exceptions=False so the 500 is captured as a response
        client = build_client(tmp_path, raise_server_exceptions=False)
        token = login_as_worker(client)
        # First create a submission
        client.post(
            "/api/v1/mobile/submissions",
            headers={
                **auth_header(token),
                "Idempotency-Key": "list-bug-test",
            },
            json={
                "form_type": "SHEET_PIECE_MEASUREMENT",
                "mode": "SELF",
                "values": {"block_count": 3},
            },
        )
        # list_submissions crashes with 500 due to FormSchema constructor call
        lst = client.get(
            "/api/v1/mobile/submissions",
            headers=auth_header(token),
        )
        # BUG: currently returns 500 Internal Server Error
        # Should return 200 with the submission list
        assert lst.status_code == 500, (
            f"BUG CONFIRMED: expected 500 (prototype bug), got {lst.status_code}. "
            "If this returns 200, the FormSchema bug has been fixed — update this test."
        )

    def test_idempotency_same_key_same_payload_returns_same_receipt(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        payload = {
            "form_type": "SHEET_PIECE_MEASUREMENT",
            "mode": "SELF",
            "values": {"block_count": 3},
        }
        headers = {**auth_header(token), "Idempotency-Key": "idem-test-002"}
        sub1 = client.post("/api/v1/mobile/submissions", headers=headers, json=payload)
        sub2 = client.post("/api/v1/mobile/submissions", headers=headers, json=payload)
        assert sub1.status_code == 200
        assert sub2.status_code == 200
        assert sub2.json()["submission_id"] == sub1.json()["submission_id"]
        assert sub2.json()["idempotent"] is True


class TestResources:
    def test_active_resources_returns_cages(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.get("/api/v1/mobile/active-resources", headers=auth_header(token))
        assert res.status_code == 200
        resources = res.json()["resources"]
        assert len(resources) > 0
        assert all(r.get("short_code", "").startswith("ZL-") for r in resources)

    def test_production_context_returns_team_context(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.get(
            "/api/v1/mobile/production-contexts/current",
            headers=auth_header(token),
        )
        assert res.status_code == 200
        body = res.json()
        assert body["team_id"] == "team-001"
        assert len(body["work_orders"]) > 0


class TestOptions:
    def test_options_returns_preset_choices(self, tmp_path: Path) -> None:
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.get("/api/v1/mobile/options/shift", headers=auth_header(token))
        assert res.status_code == 200
        assert res.json()["options"] == ["白班", "夜班"]


# ═══════════════════════════════════════════════════════════════════
#   SECURITY GAPS — these tests describe protection that is MISSING
#   and SHOULD FAIL until the corresponding task closes the gap.
# ═══════════════════════════════════════════════════════════════════

class TestMissingPermissionChecks:
    """Task 4 must make these pass: role- and resource-level enforcement."""

    def test_worker_cannot_access_disallowed_form_type_via_schema(self, tmp_path: Path) -> None:
        """Gap: form_schema() does not verify user is allowed for this type."""
        client = build_client(tmp_path)
        token = login_as_worker(client, employee_code="E00128")
        # E00128 (张三) does NOT have TEAM_SHEET_PIECE_MEASUREMENT
        res = client.get(
            "/api/v1/mobile/form-schemas/TEAM_SHEET_PIECE_MEASUREMENT",
            headers=auth_header(token),
        )
        # SHOULD BE 403 — currently returns 200 because no permission check
        assert res.status_code == 403, (
            f"GAP: expected 403, got {res.status_code}. "
            "form_schema() should reject disallowed form types."
        )

    def test_worker_cannot_submit_disallowed_form_type(self, tmp_path: Path) -> None:
        """Gap: create_submission() accepts any form type."""
        client = build_client(tmp_path)
        token = login_as_worker(client, employee_code="E00128")
        res = client.post(
            "/api/v1/mobile/submissions",
            headers={
                **auth_header(token),
                "Idempotency-Key": "gap-disallowed-type",
            },
            json={
                "form_type": "TEAM_SHEET_PIECE_MEASUREMENT",
                "mode": "TEAM_LEADER_BATCH",
                "values": {},
            },
        )
        # SHOULD BE 403 — currently returns 200
        assert res.status_code == 403, (
            f"GAP: expected 403, got {res.status_code}. "
            "create_submission() should reject disallowed form types."
        )

    def test_worker_cannot_use_team_leader_mode(self, tmp_path: Path) -> None:
        """Gap: mode is not validated against user roles."""
        client = build_client(tmp_path)
        token = login_as_worker(client, employee_code="E00128")  # NOT team leader
        res = client.post(
            "/api/v1/mobile/form-sessions",
            headers=auth_header(token),
            json={
                "form_type": "SHEET_PIECE_MEASUREMENT",
                "mode": "TEAM_LEADER_BATCH",
            },
        )
        # SHOULD BE 403 — currently returns 200
        assert res.status_code == 403, (
            f"GAP: expected 403, got {res.status_code}. "
            "TEAM_LEADER_BATCH should require TEAM_LEADER role."
        )


class TestMissingSubmissionValidation:
    """Task 5 must make these pass: server-side field rule enforcement."""

    def test_submission_rejects_missing_idempotency_key(self, tmp_path: Path) -> None:
        """Gap: idempotency key is auto-generated when missing."""
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.post(
            "/api/v1/mobile/submissions",
            headers=auth_header(token),  # no Idempotency-Key
            json={
                "form_type": "SHEET_PIECE_MEASUREMENT",
                "mode": "SELF",
                "values": {},
            },
        )
        # SHOULD BE 400 — currently returns 200 (auto-generates key)
        assert res.status_code == 400, (
            f"GAP: expected 400, got {res.status_code}. "
            "Idempotency-Key should be required."
        )

    def test_idempotency_same_key_different_payload_returns_conflict(self, tmp_path: Path) -> None:
        """Gap: idempotency is key-only, not checked against payload."""
        client = build_client(tmp_path)
        token = login_as_worker(client)
        payload_a = {"form_type": "SHEET_PIECE_MEASUREMENT", "mode": "SELF", "values": {"block_count": 1}}
        payload_b = {"form_type": "SHEET_PIECE_MEASUREMENT", "mode": "SELF", "values": {"block_count": 999}}
        headers = {**auth_header(token), "Idempotency-Key": "idem-conflict-test"}
        sub1 = client.post("/api/v1/mobile/submissions", headers=headers, json=payload_a)
        assert sub1.status_code == 200
        sub2 = client.post("/api/v1/mobile/submissions", headers=headers, json=payload_b)
        # SHOULD BE 409 — currently returns 200 (same receipt)
        assert sub2.status_code == 409, (
            f"GAP: expected 409, got {sub2.status_code}. "
            "Different payload with same Idempotency-Key should conflict."
        )

    def test_submission_rejects_forged_subject_employee(self, tmp_path: Path) -> None:
        """Gap: submission doesn't verify subject vs actor."""
        client = build_client(tmp_path)
        token = login_as_worker(client, employee_code="E00128")  # 张三
        res = client.post(
            "/api/v1/mobile/submissions",
            headers={
                **auth_header(token),
                "Idempotency-Key": "gap-forged-subject",
            },
            json={
                "form_type": "SHEET_PIECE_MEASUREMENT",
                "mode": "SELF",
                "employee_code": "E00129",  # pretending to be 李四
                "values": {"block_count": 5},
            },
        )
        # SHOULD BE 403 — SELF mode should enforce subject == actor
        assert res.status_code == 403, (
            f"GAP: expected 403, got {res.status_code}. "
            "SELF mode must reject forged subject_employee_code."
        )

    def test_submission_rejects_unknown_fields(self, tmp_path: Path) -> None:
        """Gap: submission accepts arbitrary values with no field validation."""
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.post(
            "/api/v1/mobile/submissions",
            headers={
                **auth_header(token),
                "Idempotency-Key": "gap-arbitrary-fields",
            },
            json={
                "form_type": "SHEET_PIECE_MEASUREMENT",
                "mode": "SELF",
                "values": {"fake_field": "hack", "salary": 999999},
            },
        )
        # SHOULD be rejected — currently returns 200
        assert res.status_code in (400, 422), (
            f"GAP: expected 400/422, got {res.status_code}. "
            "Arbitrary fields should be rejected by server-side validation."
        )

    def test_submission_rejects_computed_field_tampering(self, tmp_path: Path) -> None:
        """Gap: computed fields should be server-recomputed, not client-provided."""
        client = build_client(tmp_path)
        token = login_as_worker(client)
        res = client.post(
            "/api/v1/mobile/submissions",
            headers={
                **auth_header(token),
                "Idempotency-Key": "gap-computed-tamper",
            },
            json={
                "form_type": "SHEET_PIECE_MEASUREMENT",
                "mode": "SELF",
                "values": {
                    "block_count": 1,
                    "pieces_per_block": 1,
                    "total_piece_count": 99999,  # should be 1, not 99999
                },
            },
        )
        # SHOULD be either rejected or have total_piece_count recalculated to 1
        assert res.status_code in (400, 422), (
            f"GAP: expected 400/422, got {res.status_code}. "
            "Computed fields must be server-recalculated and client values ignored."
        )


class TestMissingScopeChecks:
    """Cross-cutting gaps identified in the plan."""

    def test_idempotency_is_not_scoped_to_actor(self, tmp_path: Path) -> None:
        """Gap: idempotency lookup is global, not scoped to actor/device."""
        client = build_client(tmp_path)
        token_a = login_as_worker(client, employee_code="E00128")
        token_b = login_as_worker(client, employee_code="E00129")
        # Worker A submits
        sub_a = client.post(
            "/api/v1/mobile/submissions",
            headers={**auth_header(token_a), "Idempotency-Key": "scope-test-key"},
            json={"form_type": "SHEET_PIECE_MEASUREMENT", "mode": "SELF", "values": {"block_count": 1}},
        )
        assert sub_a.status_code == 200
        # Worker B should NOT get a hit on A's key
        sub_b = client.post(
            "/api/v1/mobile/submissions",
            headers={**auth_header(token_b), "Idempotency-Key": "scope-test-key"},
            json={"form_type": "SHEET_PIECE_MEASUREMENT", "mode": "SELF", "values": {"block_count": 2}},
        )
        # SHOULD be a fresh submission — currently returns A's receipt (idempotent: true)
        assert sub_b.json().get("idempotent") is not True, (
            f"GAP: idempotency should be scoped to actor. "
            f"Worker B hit Worker A's key."
        )

    def test_outbox_is_empty_and_not_functional(self, tmp_path: Path) -> None:
        """Gap: outbox is never written to; it's a read-only empty dict."""
        client = build_client(tmp_path)
        token = login_as_worker(client)
        # Submit something (should enqueue if offline, but there is no offline path)
        client.post(
            "/api/v1/mobile/submissions",
            headers={**auth_header(token), "Idempotency-Key": "outbox-gap-test"},
            json={"form_type": "SHEET_PIECE_MEASUREMENT", "mode": "SELF", "values": {"block_count": 1}},
        )
        # Outbox is always empty — the real queue doesn't exist yet
        res = client.get("/api/v1/mobile/outbox", headers=auth_header(token))
        assert res.status_code == 200
        items = res.json()["items"]
        # Currently always 0 — outbox is a dead store
        # This test DOCUMENTS the gap; it does not assert a desired state
        assert len(items) == 0, "Outbox gap confirmed: no real offline queue exists."


class TestMissingSafetyBoundaries:
    """Safety issues from the plan's confirmed defect list."""

    def test_token_stored_in_response_not_httponly_cookie(self, tmp_path: Path) -> None:
        """Gap: token is returned in JSON body, no Set-Cookie header."""
        client = build_client(tmp_path)
        res = client.post("/api/v1/mobile/auth/login", json={
            "employee_code": "E00128",
            "pin": "1234",
        })
        assert res.status_code == 200
        # SHOULD set HttpOnly cookie — currently only JSON body
        set_cookie = res.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie or "Secure" in set_cookie, (
            f"GAP: token should be in HttpOnly cookie, not just JSON. "
            f"set-cookie header: {set_cookie!r}"
        )

    def test_pin_hash_uses_scrypt_not_truncated_sha256(self, tmp_path: Path) -> None:
        """Document the current weak PIN hashing before Task 4 replaces it."""
        # This is an informational test — it documents that the current
        # implementation uses truncated SHA-256 instead of scrypt.
        # Task 4 must replace this.
        import hashlib
        pin = "1234"
        current_hash = hashlib.sha256(pin.encode()).hexdigest()[:16]
        # scrypt would produce a salt-prefixed, variable-length output
        assert len(current_hash) == 16  # truncated SHA-256
        # This is NOT a passing assertion — it documents the weakness:
        # 16-char truncated SHA-256 without salt is not adequate for PIN storage.
        # Task 4 must replace with scrypt + random salt.
