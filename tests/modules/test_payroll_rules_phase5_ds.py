"""Phase 5 governed payroll rules — V1 Final Verification fail-closed tests.

§6.4: Full coverage of PayrollFieldRegistry validation.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    Base,
    PayrollCalculationBatchRow,
    PayrollCalculationResultRow,
    PayrollFieldRegistryRow,
)
from app.modules.payroll_rules.field_registry_seed import install_v1_field_registry
from app.modules.payroll_rules.service_ds import PayrollError, PayrollService
from app.modules.submission_ledger.service_ds import SubmissionLedgerService


@pytest.fixture
def payroll(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite:///{(tmp_path / 'payroll.db').as_posix()}")
    Base.metadata.create_all(engine)
    # V1 Final Verification §6: Seed the field registry (fail-closed)
    install_v1_field_registry(engine)
    ledger = SubmissionLedgerService(engine)
    ledger.record_acceptance(
        submission_id="SUB-1",
        factory_id="FACTORY-A",
        subject_employee_code="E001",
        actor_id="E001",
        definition_version_id="FORM-V1",
        values={"bundle_count": 10},
        submitted_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    return engine, PayrollService(engine)


def _rule(service: PayrollService, rate: str) -> dict[str, object]:
    """Create and approve a rule using a registered numeric SORT_OPERATOR field."""
    draft = service.create_rule(
        rule_key="SORT-PIECE-RATE",
        name="分选计件工资",
        factory_id="FACTORY-A",
        position="SORT_OPERATOR",
        dsl={"metric": "bundle_count", "rate": rate, "base": "0"},
        actor_id="finance-1",
    )
    service.submit_rule(str(draft["rule_version_id"]))
    return service.decide_rule(
        str(draft["rule_version_id"]),
        approved=True,
        actor_id="admin-1",
        note="批准",
    )


# ── §6.4: Fail-closed registry tests ──────────────────────────────


def test_empty_registry_position_fails(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """§6.4: Creating a rule for a position not in registry → fail."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    Base.metadata.create_all(engine)
    service = PayrollService(engine)
    with pytest.raises(PayrollError, match="PAYROLL_FIELD_REGISTRY_NOT_CONFIGURED"):
        service.create_rule(
            rule_key="TEST",
            name="测试",
            factory_id="FACTORY-A",
            position="UNREGISTERED_POSITION",
            dsl={"metric": "anything", "rate": "1", "base": "0"},
            actor_id="finance-1",
        )


def test_unknown_field_fails(payroll) -> None:  # type: ignore[no-untyped-def]
    """§6.4: Field not in registry → fail."""
    _, service = payroll
    with pytest.raises(PayrollError, match="PAYROLL_FIELD_NOT_ALLOWED"):
        service.create_rule(
            rule_key="TEST",
            name="测试",
            factory_id="FACTORY-A",
            position="SORT_OPERATOR",
            dsl={"metric": "unknown_field", "rate": "1", "base": "0"},
            actor_id="finance-1",
        )


def test_field_belongs_to_other_position_fails(payroll) -> None:  # type: ignore[no-untyped-def]
    """§6.4: DIPPING field used for SORT position → fail."""
    _, service = payroll
    with pytest.raises(PayrollError, match="PAYROLL_FIELD_NOT_ALLOWED"):
        service.create_rule(
            rule_key="TEST",
            name="测试",
            factory_id="FACTORY-A",
            position="SORT_OPERATOR",
            dsl={"metric": "glue_gain", "rate": "1", "base": "0"},
            actor_id="finance-1",
        )


def test_non_numeric_field_fails(payroll) -> None:  # type: ignore[no-untyped-def]
    """§6.4: STRING field (effective_grade) used in formula → fail."""
    _, service = payroll
    with pytest.raises(PayrollError, match="PAYROLL_FIELD_NOT_NUMERIC"):
        service.create_rule(
            rule_key="TEST",
            name="测试",
            factory_id="FACTORY-A",
            position="SORT_OPERATOR",
            dsl={"metric": "effective_grade", "rate": "1", "base": "0"},
            actor_id="finance-1",
        )


def test_valid_metric_succeeds(payroll) -> None:  # type: ignore[no-untyped-def]
    """§6.4: Valid numeric field for correct position → success."""
    _, service = payroll
    draft = service.create_rule(
        rule_key="TEST",
        name="分选把数计件",
        factory_id="FACTORY-A",
        position="SORT_OPERATOR",
        dsl={"metric": "bundle_count", "rate": "2", "base": "0"},
        actor_id="finance-1",
    )
    assert draft["status"] == "DRAFT"
    assert draft["dsl"]["metric"] == "bundle_count"


# ── Original Phase 5 tests (updated for V1 registry) ─────────────


def test_unapproved_rule_cannot_calculate(payroll) -> None:  # type: ignore[no-untyped-def]
    _, service = payroll
    draft = service.create_rule(
        rule_key="DRAFT",
        name="草稿",
        factory_id="FACTORY-A",
        position="SORT_OPERATOR",
        dsl={"metric": "bundle_count", "rate": "2", "base": "0"},
        actor_id="finance-1",
    )
    with pytest.raises(PayrollError, match="RULE_NOT_APPROVED"):
        service.calculate(
            rule_version_id=str(draft["rule_version_id"]),
            period_start="2026-07-01",
            period_end="2026-07-31",
            actor_id="finance-1",
        )


def test_calculation_binds_rule_version_and_requires_finance_confirmation(payroll) -> None:  # type: ignore[no-untyped-def]
    _, service = payroll
    rule = _rule(service, "2.50")
    batch = service.calculate(
        rule_version_id=str(rule["rule_version_id"]),
        period_start="2026-07-01",
        period_end="2026-07-31",
        actor_id="finance-1",
    )
    assert service.list_official(employee_code="E001")["items"] == []

    service.confirm_batch(str(batch["batch_id"]), actor_id="finance-2")
    item = service.list_official(employee_code="E001")["items"][0]
    assert Decimal(str(item["amount"])) == Decimal("25.00")
    assert item["rule_version_id"] == rule["rule_version_id"]


def test_historical_recalculation_keeps_old_result_and_records_delta(payroll) -> None:  # type: ignore[no-untyped-def]
    engine, service = payroll
    old_rule = _rule(service, "2.00")
    old_batch = service.calculate(
        rule_version_id=str(old_rule["rule_version_id"]),
        period_start="2026-07-01",
        period_end="2026-07-31",
        actor_id="finance-1",
    )
    service.confirm_batch(str(old_batch["batch_id"]), actor_id="finance-1")
    new_rule = _rule(service, "3.00")

    service.recalculate(
        source_batch_id=str(old_batch["batch_id"]),
        new_rule_version_id=str(new_rule["rule_version_id"]),
        actor_id="admin-1",
    )

    with Session(engine) as session:
        batches = session.scalars(select(PayrollCalculationBatchRow)).all()
        results = session.scalars(
            select(PayrollCalculationResultRow).order_by(
                PayrollCalculationResultRow.created_at
            )
        ).all()
    assert len(batches) == 2
    assert batches[0].status == "CONFIRMED"
    assert batches[1].status == "PENDING_FINANCE"
    assert [row.amount for row in results] == ["20.00", "30.00"]
    assert results[1].original_amount == "20.00"
    assert results[1].delta_amount == "10.00"
    assert service.list_official(employee_code="E001")["items"][0]["amount"] == "20.00"


def test_draft_trial_calculation(payroll) -> None:  # type: ignore[no-untyped-def]
    """§9.3: DRAFT rules can be trialed (dry_run)."""
    _, service = payroll
    draft = service.create_rule(
        rule_key="TRIAL-TEST",
        name="试算测试",
        factory_id="FACTORY-A",
        position="SORT_OPERATOR",
        dsl={"metric": "bundle_count", "rate": "3", "base": "0"},
        actor_id="finance-1",
    )
    # DRAFT should allow dry_run
    trial = service.calculate(
        rule_version_id=str(draft["rule_version_id"]),
        period_start="2026-07-01",
        period_end="2026-07-31",
        actor_id="finance-1",
        dry_run=True,
    )
    assert trial["dry_run"] is True
    assert trial["result_count"] >= 0
