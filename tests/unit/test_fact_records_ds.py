"""FactRecord domain model and transformation tests."""

import pytest

from app.application.transform_facts import (
    transform_electronic_submission,
    transform_paper_confirmation,
)
from app.modules.electronic_forms.models_ds import (
    ElectronicSubmissionReceipt,
    ReceiptOperation,
    SubmissionReceiptStatus,
)
from app.modules.fact_records.models_ds import (
    FactExportStatus,
    FactRecord,
    FactReviewStatus,
    FactSourceType,
)


def _receipt(
    subject_employee_code: str = "E00128",
    receipt_id: str = "REC-1",
) -> ElectronicSubmissionReceipt:
    return ElectronicSubmissionReceipt(
        receipt_id=receipt_id,
        actor_id="E00128",
        subject_employee_code=subject_employee_code,
        device_id="device-1",
        operation=ReceiptOperation.CREATE_ELECTRONIC_FORM,
        client_submission_id="client-1",
        payload_hash="abc123",
        status=SubmissionReceiptStatus.ACCEPTED,
    )


# ── FactRecord domain behaviour ─────────────────────────────────


class TestFactRecordDomain:
    def test_new_record_is_pending_and_not_exported(self) -> None:
        record = FactRecord(
            fact_record_id="FR-1",
            source_type=FactSourceType.ELECTRONIC,
            subject_employee_code="E00128",
        )
        assert record.review_status == FactReviewStatus.PENDING
        assert record.export_status == FactExportStatus.NOT_EXPORTED

    def test_confirm_transitions_to_confirmed(self) -> None:
        record = FactRecord(
            fact_record_id="FR-1",
            source_type=FactSourceType.ELECTRONIC,
            subject_employee_code="E00128",
        )
        record.confirm("reviewer-1")
        assert record.review_status == FactReviewStatus.CONFIRMED
        assert record.reviewed_by == "reviewer-1"
        assert record.reviewed_at is not None

    def test_confirm_on_already_confirmed_raises(self) -> None:
        record = FactRecord(
            fact_record_id="FR-1",
            source_type=FactSourceType.ELECTRONIC,
            subject_employee_code="E00128",
        )
        record.confirm("reviewer-1")
        with pytest.raises(ValueError, match="Cannot confirm"):
            record.confirm("reviewer-2")

    def test_correct_produces_snapshot_and_sets_reexport(self) -> None:
        record = FactRecord(
            fact_record_id="FR-1",
            source_type=FactSourceType.ELECTRONIC,
            subject_employee_code="E00128",
            blocks_completed=10,
            pieces_per_block=25,
            total_pieces=250,
        )
        record.confirm("reviewer-1")
        record.mark_exported()

        snapshot = record.correct(
            "reviewer-2",
            {"blocks_completed": 12, "total_pieces": 300},
            "miscount",
        )
        assert record.review_status == FactReviewStatus.CORRECTED
        assert record.export_status == FactExportStatus.REEXPORT_REQUIRED
        assert record.blocks_completed == 12
        assert record.total_pieces == 300
        assert snapshot["before"]["blocks_completed"] == 10
        assert snapshot["after"]["blocks_completed"] == 12
        assert len(record.corrections) == 1

    def test_return_for_correction_adds_anomaly(self) -> None:
        record = FactRecord(
            fact_record_id="FR-1",
            source_type=FactSourceType.ELECTRONIC,
            subject_employee_code="E00128",
        )
        record.return_for_correction("reviewer-1", "missing work order")
        assert record.review_status == FactReviewStatus.RETURNED
        assert len(record.anomalies) == 1
        assert record.anomalies[0]["code"] == "RETURNED"

    def test_void_adds_blocking_anomaly(self) -> None:
        record = FactRecord(
            fact_record_id="FR-1",
            source_type=FactSourceType.ELECTRONIC,
            subject_employee_code="E00128",
        )
        record.void("admin", "duplicate entry")
        assert record.review_status == FactReviewStatus.VOIDED
        assert record.anomalies[0]["severity"] == "BLOCKING"

    def test_mark_exported_sets_status(self) -> None:
        record = FactRecord(
            fact_record_id="FR-1",
            source_type=FactSourceType.ELECTRONIC,
            subject_employee_code="E00128",
        )
        record.mark_exported()
        assert record.export_status == FactExportStatus.EXPORTED


# ── Transformation tests ────────────────────────────────────────


class TestPersonalSubmissionTransform:
    def test_personal_submission_creates_one_record(self) -> None:
        receipt = _receipt("E00128")
        payload = {
            "values": {
                "production_date": "2026-07-21",
                "shift": "白班",
                "blocks_completed": 18,
                "pieces_per_block": 24,
                "workshop": "配片一组",
                "work_order_id": "WO-001",
            }
        }
        records = transform_electronic_submission(receipt, payload, employee_name="张三")

        assert len(records) == 1
        record = records[0]
        assert record.source_type == FactSourceType.ELECTRONIC
        assert record.source_submission_id == "REC-1"
        assert record.subject_employee_code == "E00128"
        assert record.subject_employee_name == "张三"
        assert record.production_date == "2026-07-21"
        assert record.shift == "白班"
        assert record.blocks_completed == 18
        assert record.pieces_per_block == 24
        assert record.total_pieces == 432  # 18 * 24
        assert record.review_status == FactReviewStatus.PENDING

    def test_personal_submission_with_total_pieces_fallback(self) -> None:
        receipt = _receipt("E00128")
        payload = {
            "values": {
                "production_date": "2026-07-21",
                "total_pieces": 500,
            }
        }
        records = transform_electronic_submission(receipt, payload)
        assert records[0].total_pieces == 500

    def test_personal_submission_extracts_measurements(self) -> None:
        receipt = _receipt("E00128")
        payload = {
            "values": {
                "temperature": 120.5,
                "humidity": 65,
                "weight": 12.3,
                "blocks_completed": 10,
                "pieces_per_block": 20,
            }
        }
        records = transform_electronic_submission(receipt, payload)
        measurements = records[0].measurement_values
        assert measurements == {"temperature": 120.5, "humidity": 65, "weight": 12.3}


class TestTeamSubmissionTransform:
    def test_team_submission_creates_one_record_per_member(self) -> None:
        receipt = _receipt("E00129")  # team leader
        payload = {
            "values": {
                "production_date": "2026-07-21",
                "shift": "白班",
                "work_order_id": "WO-001",
            },
            "team_members": [
                {
                    "employee_code": "E00128",
                    "employee_name": "张三",
                    "values": {"blocks_completed": 18, "pieces_per_block": 24},
                },
                {
                    "employee_code": "E00130",
                    "employee_name": "王五",
                    "values": {"blocks_completed": 20, "pieces_per_block": 24},
                },
            ],
        }
        records = transform_electronic_submission(receipt, payload)

        assert len(records) == 2

        zhang = next(r for r in records if r.subject_employee_code == "E00128")
        assert zhang.subject_employee_name == "张三"
        assert zhang.blocks_completed == 18
        assert zhang.total_pieces == 432
        assert zhang.work_order_id == "WO-001"  # merged from team-level values

        wang = next(r for r in records if r.subject_employee_code == "E00130")
        assert wang.subject_employee_name == "王五"
        assert wang.blocks_completed == 20
        assert wang.total_pieces == 480

        # Both share the same source submission
        assert zhang.source_submission_id == "REC-1"
        assert wang.source_submission_id == "REC-1"


class TestPaperConfirmationTransform:
    def test_paper_confirmation_creates_record(self) -> None:
        confirmed_values = {
            "employee_id": "E00128",
            "employee_name": "张三",
            "production_date": "2026-07-21",
            "blocks_completed": 15,
            "pieces_per_block": 24,
            "workshop": "配片一组",
        }
        record = transform_paper_confirmation(
            "FORM-1",
            confirmed_values,
        )
        assert record.source_type == FactSourceType.PAPER_OCR
        assert record.source_form_id == "FORM-1"
        assert record.subject_employee_code == "E00128"
        assert record.subject_employee_name == "张三"
        assert record.total_pieces == 360  # 15 * 24

    def test_paper_confirmation_uses_explicit_args(self) -> None:
        record = transform_paper_confirmation(
            "FORM-2",
            {"blocks_completed": 10, "pieces_per_block": 30},
            employee_code="E00999",
            employee_name="赵六",
        )
        assert record.subject_employee_code == "E00999"
        assert record.subject_employee_name == "赵六"
        assert record.total_pieces == 300
