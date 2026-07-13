from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import create_engine

from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.database.template_repository_ds import SqlAlchemyTemplateRepository
from app.adapters.recognition.candidate import RecognitionCandidate
from app.adapters.recognition.opencv import OpenCvImagePipeline
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.import_forms import ImportForms
from app.application.query_forms import QueryForms
from app.application.recognize_forms import RecognizeForms
from app.application.review_forms import ReviewForms
from app.domain.models import FormField, ReviewStatus
from app.domain.templates_ds import (
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateVersion,
    build_template_payload,
)


def build(tmp_path: Path):  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    template_repository = SqlAlchemyTemplateRepository(engine)
    storage = LocalEvidenceStorage(tmp_path / "evidence")
    imports = ImportForms(repository, repository, repository, storage)
    recognizer = RecognizeForms(
        repository,
        repository,
        repository,
        storage,
        OpenCvImagePipeline(),
        template_repository,
    )
    return imports, recognizer, repository, template_repository


def test_recognition_attempts_append_and_never_change_confirmed_values(tmp_path: Path) -> None:
    imports, recognizer, repository, _ = build(tmp_path)
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    evidence = imports.import_image(image, "FORM-0001", "T1", "1", "operator")
    repository.add_form_field(
        FormField(
            "FIELD-1", "FORM-0001", "total_quantity", {"x": 0, "y": 0, "width": 48, "height": 64}
        )
    )
    ReviewForms(repository, repository).confirm(
        "FORM-0001", 0, {"total_quantity": 8}, "reviewer", "confirmed", (evidence.file_id,)
    )
    before_version = repository.get_form("FORM-0001").current_record_version  # type: ignore[union-attr]
    crop = np.full((64, 48), 255, dtype=np.uint8)
    cv2.putText(crop, "7", (6, 53), cv2.FONT_HERSHEY_SIMPLEX, 1.8, 0, 3, cv2.LINE_AA)
    candidate = RecognitionCandidate("7", 0.95, "test-engine", "v1", "OK")

    recognizer.record_candidate("FORM-0001", "FIELD-1", crop, candidate, "recognizer")
    recognizer.record_candidate("FORM-0001", "FIELD-1", cv2.flip(crop, 1), candidate, "recognizer")

    attempts = repository.list_recognition_attempts("FIELD-1")
    assert len(attempts) == 2
    assert attempts[0].candidate_value == "7"
    assert attempts[0].crop_file_id != attempts[1].crop_file_id
    assert repository.get_form("FORM-0001").current_record_version == before_version  # type: ignore[union-attr]
    assert repository.list_record_versions("FORM-0001")[-1].values == {"total_quantity": 8}
    trace = QueryForms(repository).trace("FORM-0001")
    assert len(trace.attempts) == 2
    assert len([item for item in trace.evidence if item.related_field_id == "FIELD-1"]) == 2


def test_missing_qr_requires_classification_and_manual_choice_is_audited(tmp_path: Path) -> None:
    imports, recognizer, repository, _ = build(tmp_path)
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    imports.import_image(image, "FORM-0001", "UNKNOWN", "1", "operator")

    result = recognizer.classify_image("FORM-0001", np.full((200, 200), 255, dtype=np.uint8))
    assert result.template_reference is None
    assert repository.get_form("FORM-0001").review_status is ReviewStatus.NEEDS_CLASSIFICATION  # type: ignore[union-attr]

    recognizer.manual_reclassify("FORM-0001", "T2", "3", "reviewer", "QR damaged")

    restored = repository.get_form("FORM-0001")
    assert restored is not None
    assert (restored.template_id, restored.template_version) == ("T2", "3")
    assert restored.review_status is ReviewStatus.CLASSIFIED
    assert repository.list_audit_events("FORM-0001")[-1].event_type == "RECLASSIFY"


def test_non_ifd_or_tampered_qr_requires_manual_classification(tmp_path: Path) -> None:
    imports, recognizer, repository, _ = build(tmp_path)
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    imports.import_image(image, "FORM-0001", "UNKNOWN", "1", "operator")
    tampered_qr = cv2.QRCodeEncoder_create().encode("IFD|PAYROLL_HOURLY|1|FFFF")

    result = recognizer.classify_image("FORM-0001", tampered_qr)

    assert result.template_reference is None
    restored = repository.get_form("FORM-0001")
    assert restored is not None
    assert restored.review_status is ReviewStatus.NEEDS_CLASSIFICATION


def test_valid_but_unpublished_ifd_requires_manual_classification(tmp_path: Path) -> None:
    imports, recognizer, repository, template_repository = build(tmp_path)
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    imports.import_image(image, "FORM-0001", "UNKNOWN", "1", "operator")
    template_repository.add_version(
        TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 3, PageSpec.a4_portrait())
    )
    qr = cv2.QRCodeEncoder_create().encode(build_template_payload("PAYROLL_HOURLY", 3))

    result = recognizer.classify_image("FORM-0001", qr)

    assert result.template_reference is None
    restored = repository.get_form("FORM-0001")
    assert restored is not None
    assert restored.review_status is ReviewStatus.NEEDS_CLASSIFICATION


def test_valid_ifd_qr_binds_the_exact_template_key_and_version(tmp_path: Path) -> None:
    imports, recognizer, repository, template_repository = build(tmp_path)
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    imports.import_image(image, "FORM-0001", "UNKNOWN", "1", "operator")
    payload = build_template_payload("PAYROLL_HOURLY", 3)
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 3, PageSpec.a4_portrait())
    version.mark_ready_to_publish()
    version.publish()
    template_repository.add_version(version)
    qr = cv2.QRCodeEncoder_create().encode(payload)

    result = recognizer.classify_image("FORM-0001", qr)

    assert result.template_reference == payload
    restored = repository.get_form("FORM-0001")
    assert restored is not None
    assert (restored.template_id, restored.template_version) == ("PAYROLL_HOURLY", "3")


def test_canonical_canvas_yields_immutable_template_field_crop_evidence(tmp_path: Path) -> None:
    imports, recognizer, repository, _ = build(tmp_path)
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    imports.import_image(image, "FORM-0001", "PAYROLL_HOURLY", "1", "operator")
    page = PageSpec.a5_portrait()
    template = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, page)
    template.add_field(
        FieldDefinition(
            "total_quantity",
            "Total",
            "integer",
            "digit_boxes",
            Rect(0.1, 0.2, 0.2, 0.1),
            page,
            recognition_engine="digit_template",
        )
    )
    canvas = np.full((page.canonical_height_px, page.canonical_width_px), 255, dtype=np.uint8)
    crops = recognizer.record_template_field_crops("FORM-0001", canvas, template)

    assert set(crops) == {"total_quantity"}
    assert crops["total_quantity"].type.value == "FIELD_CROP"
    assert crops["total_quantity"].related_field_id == "FORM-0001:TPL-1:total_quantity"
    assert repository.list_form_fields("FORM-0001")[0].field_id == "FORM-0001:TPL-1:total_quantity"
    attempts = repository.list_recognition_attempts("FORM-0001:TPL-1:total_quantity")
    assert len(attempts) == 1
    assert attempts[0].engine == "opencv-template-digit"
    assert len(repository.list_evidence("FORM-0001")) == 2
