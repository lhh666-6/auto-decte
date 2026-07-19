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
from app.adapters.templates.print_renderer_ds import TemplatePrintRenderer
from app.application.import_forms import ImportForms
from app.application.query_forms import QueryForms
from app.application.recognize_forms import RecognizeForms
from app.application.review_forms import ReviewForms
from app.domain.models import FormField, ReviewStatus
from app.domain.templates_ds import (
    CoreLayoutKind,
    FieldDefinition,
    PageSpec,
    PayrollJobProfileVersion,
    Rect,
    TemplateVersion,
    build_sheet_payload,
    build_template_payload,
    build_template_profile_payload,
)
from app.modules.templates.payroll_profiles_ds import reviewed_payroll_seed_templates


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


def test_all_reviewed_print_pngs_route_to_their_exact_published_versions(
    tmp_path: Path,
) -> None:
    imports, recognizer, repository, template_repository = build(tmp_path)
    renderer = TemplatePrintRenderer(tmp_path / "prints")

    for index, template in enumerate(reviewed_payroll_seed_templates(), start=1):
        template_repository.add_version(template)
        source = tmp_path / f"source-{index}.png"
        source.write_bytes(f"source-{index}".encode())
        form_id = f"FORM-PROFILE-{index:02d}"
        imports.import_image(source, form_id, "UNKNOWN", "0", "operator")
        artifact = next(
            item for item in renderer.render(template) if item.kind == "PRINT_PNG"
        )
        image = cv2.imread(artifact.internal_uri)

        result = recognizer.classify_image(form_id, image)
        restored = repository.get_form(form_id)

        assert result.source == "QR"
        assert result.template_reference == build_template_payload(
            template.template_key,
            template.version,
        )
        assert restored is not None
        assert (restored.template_id, restored.template_version) == (
            template.template_key,
            str(template.version),
        )


def test_dual_version_qr_routes_to_published_template_and_job_profile(
    tmp_path: Path,
) -> None:
    imports, recognizer, repository, template_repository = build(tmp_path)
    template = TemplateVersion.draft(
        "TPL-TIMEKEEPING-V2", "CORE_TIMEKEEPING", 2, PageSpec.a5_landscape()
    )
    template.mark_ready_to_publish()
    template.publish()
    profile = PayrollJobProfileVersion.draft(
        "PROFILE-DAY-V4",
        "TIMEKEEPING_DAY",
        4,
        display_name="计时工白班",
        core_layout=CoreLayoutKind.TIMEKEEPING,
        template_version_id=template.version_id,
        template_version=template.version,
    )
    profile.mark_ready_to_publish()
    profile.publish()
    template_repository.add_version(template)
    template_repository.add_job_profile(profile)
    source = tmp_path / "dual-version-source.png"
    source.write_bytes(b"dual-version")
    imports.import_image(source, "FORM-DUAL", "UNKNOWN", "0", "operator")
    artifact = next(
        item
        for item in TemplatePrintRenderer(tmp_path / "prints").render(
            template, job_profile=profile
        )
        if item.kind == "PRINT_PNG"
    )

    result = recognizer.classify_image("FORM-DUAL", cv2.imread(artifact.internal_uri))
    restored = repository.get_form("FORM-DUAL")

    assert result.template_reference == build_template_profile_payload(
        template.template_key, template.version, profile.profile_key, profile.version
    )
    assert result.job_profile_key == profile.profile_key
    assert result.job_profile_version == profile.version
    assert restored is not None
    assert restored.job_profile_key == profile.profile_key
    assert restored.job_profile_version == str(profile.version)


def test_unknown_job_profile_in_dual_qr_requires_manual_classification(
    tmp_path: Path,
) -> None:
    imports, recognizer, repository, template_repository = build(tmp_path)
    template = TemplateVersion.draft(
        "TPL-TIMEKEEPING-V2", "CORE_TIMEKEEPING", 2, PageSpec.a5_landscape()
    )
    template.mark_ready_to_publish()
    template.publish()
    template_repository.add_version(template)
    source = tmp_path / "unknown-profile.png"
    source.write_bytes(b"unknown-profile")
    imports.import_image(source, "FORM-UNKNOWN-PROFILE", "UNKNOWN", "0", "operator")
    payload = build_template_profile_payload(
        template.template_key, template.version, "MISSING_PROFILE", 1
    )
    qr = cv2.QRCodeEncoder_create().encode(payload)

    result = recognizer.classify_image("FORM-UNKNOWN-PROFILE", qr)
    restored = repository.get_form("FORM-UNKNOWN-PROFILE")

    assert result.source == "NONE"
    assert restored is not None
    assert restored.review_status is ReviewStatus.NEEDS_CLASSIFICATION


def test_two_up_crops_prioritize_their_independent_sheet_qrs(
    tmp_path: Path,
) -> None:
    imports, recognizer, repository, template_repository = build(tmp_path)
    template = reviewed_payroll_seed_templates()[0]
    template_repository.add_version(template)
    imposed = TemplatePrintRenderer(tmp_path / "prints").compose_imposition(
        template,
        print_batch="PB20260719B",
        first_sequence=71,
    )
    halves = (
        np.asarray(imposed.crop((0, 0, imposed.width // 2, imposed.height)).convert("RGB")),
        np.asarray(
            imposed.crop((imposed.width // 2, 0, imposed.width, imposed.height)).convert("RGB")
        ),
    )

    for offset, image in enumerate(halves):
        form_id = f"FORM-TWO-UP-{offset + 1}"
        source = tmp_path / f"two-up-{offset + 1}.png"
        source.write_bytes(f"two-up-{offset + 1}".encode())
        imports.import_image(source, form_id, "UNKNOWN", "0", "operator")

        result = recognizer.classify_image(form_id, image)
        restored = repository.get_form(form_id)

        assert result.source == "SHEET_QR"
        assert result.sheet_reference == build_sheet_payload(
            "PB20260719B",
            71 + offset,
        )
        assert restored is not None
        assert (restored.template_id, restored.template_version) == (
            template.template_key,
            "1",
        )


def test_conflicting_template_qrs_require_manual_classification_and_are_audited(
    tmp_path: Path,
) -> None:
    imports, recognizer, repository, template_repository = build(tmp_path)
    templates = reviewed_payroll_seed_templates()[:2]
    for template in templates:
        template_repository.add_version(template)
    source = tmp_path / "conflict.png"
    source.write_bytes(b"conflict")
    imports.import_image(source, "FORM-CONFLICT", "UNKNOWN", "0", "operator")
    canvas = np.full((360, 720), 255, dtype=np.uint8)
    expected_references: list[str] = []
    for index, template in enumerate(templates):
        reference = build_template_payload(template.template_key, template.version)
        expected_references.append(reference)
        qr = cv2.QRCodeEncoder_create().encode(reference)
        qr = np.pad(qr, 4, mode="constant", constant_values=255)
        qr = cv2.resize(qr, (260, 260), interpolation=cv2.INTER_NEAREST)
        left = 60 + index * 340
        canvas[50:310, left : left + 260] = qr

    result = recognizer.classify_image("FORM-CONFLICT", canvas)
    restored = repository.get_form("FORM-CONFLICT")
    audit = repository.list_audit_events("FORM-CONFLICT")[-1]

    assert result.source == "CONFLICT"
    assert result.conflict_references == tuple(sorted(expected_references))
    assert restored is not None
    assert restored.review_status is ReviewStatus.NEEDS_CLASSIFICATION
    assert (restored.template_id, restored.template_version) == ("UNKNOWN", "0")
    assert audit.event_type == "CLASSIFICATION_CONFLICT"
    assert audit.after["references"] == sorted(expected_references)


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
