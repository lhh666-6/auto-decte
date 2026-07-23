"""Test electronic submission integration into the review workflow (Task 5)."""

import pytest

from app.application.electronic_submissions_ds import (
    ElectronicFormCommand,
    ElectronicFormIntegration,
    IdempotencyConflict,
)
from app.domain.models import AuditEvent, Form, FormField
from app.modules.electronic_forms.models_ds import (
    ElectronicSubmissionReceipt,
    SubmissionReceiptStatus,
)


class _FakeForms:
    """Records form writes for assertion without touching a database."""

    def __init__(self) -> None:
        self.calls: list[tuple[Form, list[FormField], AuditEvent]] = []
        self._form: Form | None = None
        self._fields: list[FormField] = []

    def add_form(self, form: Form) -> None:
        self._form = form

    def add_form_field(self, field: FormField) -> None:
        self._fields.append(field)

    def add_audit_event(self, audit: AuditEvent) -> None:
        assert self._form is not None
        self.calls.append((self._form, self._fields, audit))


class _FakeReceiptRepo:
    def __init__(self) -> None:
        self.store: dict[str, ElectronicSubmissionReceipt] = {}

    def add(self, r: ElectronicSubmissionReceipt) -> None:
        self.store[r.receipt_id] = r

    def find_idempotent(
        self,
        actor_id: str,
        device_id: str,
        operation: str,
        client_submission_id: str,
    ) -> ElectronicSubmissionReceipt | None:
        for r in self.store.values():
            if (
                r.actor_id == actor_id
                and r.device_id == device_id
                and r.operation.value == operation
                and r.client_submission_id == client_submission_id
            ):
                return r
        return None


class _FakeFactRecordRepo:
    def __init__(self) -> None:
        self.records = []

    def add(self, record) -> None:  # type: ignore[no-untyped-def]
        self.records.append(record)


class _FakeUnitOfWork:
    def __init__(self) -> None:
        self.forms = _FakeForms()
        self.receipts = _FakeReceiptRepo()
        self.facts = _FakeFactRecordRepo()
        self.finance_acceptances: list[tuple[object, object]] = []

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *args) -> None:  # type: ignore[no-untyped-def]
        return None

    def flush(self) -> None:
        return None

    def record_finance_acceptance(self, receipt, command) -> None:  # type: ignore[no-untyped-def]
        self.finance_acceptances.append((receipt, command))


def _make_command(**overrides) -> ElectronicFormCommand:
    defaults = {
        "form_type": "SHEET_PIECE_MEASUREMENT",
        "definition_version_id": "efd-v1",
        "mode": "SELF",
        "actor_id": "actor-1",
        "subject_employee_code": "E001",
        "subject_employee_name": "张三",
        "team_id": "team-001",
        "team_name": "配片一组",
        "device_id": "dev-a",
        "values": {"block_count": 5, "pieces_per_block": 24},
        "client_submission_id": "cs-test",
        "template_id": "TPL-SHEET",
        "template_version": "1",
    }
    return ElectronicFormCommand(**{**defaults, **overrides})


@pytest.fixture
def integration() -> ElectronicFormIntegration:
    uow = _FakeUnitOfWork()
    return ElectronicFormIntegration(uow_factory=lambda: uow)


def _fake_uow(integration: ElectronicFormIntegration) -> _FakeUnitOfWork:
    return integration._uow_factory()  # type: ignore[return-value]


class TestElectronicSubmission:
    def test_accept_creates_form_in_needs_review(
        self, integration: ElectronicFormIntegration
    ) -> None:
        cmd = _make_command()
        receipt = integration.accept(cmd)

        assert receipt.form_id is not None
        assert receipt.form_id.startswith("EF-")
        assert receipt.status == SubmissionReceiptStatus.NEEDS_REVIEW

        creator = _fake_uow(integration).forms
        assert len(creator.calls) == 1
        form, fields, audit = creator.calls[0]
        assert form.review_status.value == "NEEDS_REVIEW"
        assert form.template_id == "TPL-SHEET"

    def test_fields_have_electronic_submitted_source(
        self, integration: ElectronicFormIntegration
    ) -> None:
        cmd = _make_command(values={"block_count": 8})
        integration.accept(cmd)

        creator = _fake_uow(integration).forms
        _, fields, _ = creator.calls[0]
        assert len(fields) == 1
        assert fields[0].field_name == "block_count"
        assert fields[0].current_value == 8
        assert fields[0].current_value_source.value == "ELECTRONIC_SUBMITTED"

    def test_audit_event_records_electronic_submit(
        self, integration: ElectronicFormIntegration
    ) -> None:
        cmd = _make_command()
        integration.accept(cmd)

        creator = _fake_uow(integration).forms
        _, _, audit = creator.calls[0]
        assert audit.event_type == "ELECTRONIC_SUBMIT"
        assert audit.actor_id == "actor-1"
        assert audit.after["subject_employee_code"] == "E001"  # type: ignore[index]

    def test_idempotent_replay_returns_same_receipt(
        self, integration: ElectronicFormIntegration
    ) -> None:
        cmd = _make_command(client_submission_id="cs-replay")
        r1 = integration.accept(cmd)
        r2 = integration.accept(cmd)
        assert r1.receipt_id == r2.receipt_id
        # Form creator only called once
        creator = _fake_uow(integration).forms
        assert len(creator.calls) == 1

    def test_idempotent_conflict_different_payload(
        self, integration: ElectronicFormIntegration
    ) -> None:
        cmd1 = _make_command(client_submission_id="cs-conflict", values={"block_count": 1})
        integration.accept(cmd1)
        cmd2 = _make_command(client_submission_id="cs-conflict", values={"block_count": 999})
        with pytest.raises(IdempotencyConflict):
            integration.accept(cmd2)

    def test_receipt_has_payload_hash(self, integration: ElectronicFormIntegration) -> None:
        cmd = _make_command(values={"x": 1, "y": 2})
        receipt = integration.accept(cmd)
        assert len(receipt.payload_hash) == 64  # SHA-256 hex

    def test_accept_generates_fact_records_when_repo_provided(self) -> None:
        """FactRecords are created after a successful submission acceptance."""
        uow = _FakeUnitOfWork()
        integration = ElectronicFormIntegration(uow_factory=lambda: uow)
        cmd = _make_command(
            values={
                "production_date": "2026-07-21",
                "shift": "白班",
                "blocks_completed": 10,
                "pieces_per_block": 24,
                "workshop": "配片一组",
            },
        )
        integration.accept(cmd)

        assert len(uow.facts.records) == 1
        record = uow.facts.records[0]
        assert record.subject_employee_code == "E001"
        assert record.subject_employee_name == "张三"
        assert record.blocks_completed == 10
        assert record.total_pieces == 240
        assert record.source_type.value == "ELECTRONIC"
