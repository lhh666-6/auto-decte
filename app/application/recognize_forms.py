"""Classification and append-only recognition orchestration."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import cv2
from numpy.typing import NDArray

from app.adapters.recognition.candidate import RecognitionCandidate
from app.adapters.recognition.digits import DigitRecognizer
from app.adapters.recognition.omr import OmrRecognizer
from app.adapters.recognition.opencv import FieldRegion, OpenCvImagePipeline, QualityAssessment
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.ports import AuditRepository, EvidenceRepository, FormRepository
from app.domain.models import (
    AuditEvent,
    EvidenceFile,
    EvidenceType,
    Form,
    FormField,
    RecognitionAttempt,
    ReviewStatus,
)
from app.domain.templates_ds import (
    JobProfileStatus,
    PayrollJobProfileVersion,
    TemplateStatus,
    TemplateVersion,
    parse_sheet_payload,
    parse_template_payload,
    parse_template_profile_payload,
)


class RecognitionRepository(Protocol):
    def add_recognition_attempt(self, attempt: RecognitionAttempt) -> None: ...
    def set_template(
        self,
        form_id: str,
        template_id: str,
        template_version: str,
        status: ReviewStatus,
        job_profile_key: str | None = None,
        job_profile_version: str | None = None,
    ) -> None: ...


class TemplateVersionResolver(Protocol):
    """Resolve the exact immutable template version declared by a QR code."""

    def get_version_by_key_version(
        self, template_key: str, version: int
    ) -> TemplateVersion | None: ...

    def get_job_profile_by_key_version(
        self, profile_key: str, version: int
    ) -> PayrollJobProfileVersion | None: ...


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    template_reference: str | None
    source: str
    confidence: float
    sheet_reference: str | None = None
    job_profile_key: str | None = None
    job_profile_version: int | None = None
    conflict_references: tuple[str, ...] = ()


class RecognizeForms:
    def __init__(
        self,
        forms: FormRepository,
        evidence: EvidenceRepository,
        audits: AuditRepository,
        storage: LocalEvidenceStorage,
        pipeline: OpenCvImagePipeline,
        template_versions: TemplateVersionResolver | None = None,
    ) -> None:
        self._forms = forms
        self._evidence = evidence
        self._audits = audits
        self._recognition: RecognitionRepository = forms  # type: ignore[assignment]
        self._storage = storage
        self._pipeline = pipeline
        self._template_versions = template_versions
        self._digits = DigitRecognizer()
        self._omr = OmrRecognizer()

    def assess_quality(self, image: NDArray[Any]) -> QualityAssessment:
        return self._pipeline.assess_quality(image)

    def classify_image(self, form_id: str, image: NDArray[Any]) -> ClassificationResult:
        form = self._require_form(form_id)
        references = self._pipeline.read_qr_payloads(image)
        profile_references = {
            profile_candidate: reference
            for reference in references
            if (profile_candidate := parse_template_profile_payload(reference)) is not None
        }
        template_references = {
            template_candidate: reference
            for reference in references
            if (template_candidate := parse_template_payload(reference)) is not None
        }
        sheet_references = {
            sheet_candidate: reference
            for reference in references
            if (sheet_candidate := parse_sheet_payload(reference)) is not None
        }
        if (
            len(profile_references) > 1
            or len(template_references) > 1
            or len(sheet_references) > 1
            or (profile_references and template_references)
        ):
            conflicts = tuple(
                sorted(
                    (
                        *profile_references.values(),
                        *template_references.values(),
                        *sheet_references.values(),
                    )
                )
            )
            self._mark_classification_conflict(form, conflicts)
            return ClassificationResult(None, "CONFLICT", 0.0, conflict_references=conflicts)
        profile_identity, profile_reference = next(
            iter(profile_references.items()), (None, None)
        )
        legacy_identity, legacy_reference = next(
            iter(template_references.items()), (None, None)
        )
        selected_template_identity = (
            (profile_identity[0], profile_identity[1])
            if profile_identity is not None
            else legacy_identity
        )
        reference = profile_reference or legacy_reference
        sheet_reference = next(iter(sheet_references.values()), None)
        template = (
            self._template_versions.get_version_by_key_version(*selected_template_identity)
            if selected_template_identity is not None and self._template_versions is not None
            else None
        )
        profile = (
            self._template_versions.get_job_profile_by_key_version(
                profile_identity[2], profile_identity[3]
            )
            if profile_identity is not None and self._template_versions is not None
            else None
        )
        valid_profile = profile_identity is None or (
            profile is not None
            and profile.status is JobProfileStatus.PUBLISHED
            and template is not None
            and profile.template_version_id == template.version_id
            and profile.template_version == template.version
        )
        if (
            selected_template_identity is not None
            and template is not None
            and template.status is TemplateStatus.PUBLISHED
            and valid_profile
        ):
            template_id, version_number = selected_template_identity
            version = str(version_number)
            self._recognition.set_template(
                form_id,
                template_id,
                version,
                ReviewStatus.CLASSIFIED,
                profile.profile_key if profile is not None else None,
                str(profile.version) if profile is not None else None,
            )
            source = "SHEET_QR" if sheet_reference is not None else "QR"
            self._audit_classification(
                form,
                template_id,
                version,
                source,
                sheet_reference=sheet_reference,
                job_profile_key=profile.profile_key if profile is not None else None,
                job_profile_version=str(profile.version) if profile is not None else None,
            )
            return ClassificationResult(
                reference,
                source,
                1.0,
                sheet_reference,
                profile.profile_key if profile is not None else None,
                profile.version if profile is not None else None,
            )
        self._forms.set_review_status(form_id, ReviewStatus.NEEDS_CLASSIFICATION)
        return ClassificationResult(None, "NONE", 0.0)

    def manual_reclassify(
        self,
        form_id: str,
        template_id: str,
        template_version: str,
        actor_id: str,
        reason: str,
    ) -> None:
        form = self._require_form(form_id)
        self._recognition.set_template(
            form_id, template_id, template_version, ReviewStatus.CLASSIFIED
        )
        self._audits.add_audit_event(
            AuditEvent(
                event_id=f"EVENT-{uuid4().hex}",
                form_id=form_id,
                event_type="RECLASSIFY",
                actor_id=actor_id,
                before={
                    "template_id": form.template_id,
                    "template_version": form.template_version,
                },
                after={"template_id": template_id, "template_version": template_version},
                reason=reason,
            )
        )

    def correct_and_record_template_canvas(
        self,
        form_id: str,
        image: NDArray[Any],
        *,
        width: int,
        height: int,
        canonical_dpi: int = 300,
    ) -> tuple[EvidenceFile, NDArray[Any]]:
        """Persist a derived canonical canvas without overwriting the original evidence."""
        self._require_form(form_id)
        corrected = self._pipeline.correct_template_perspective(
            image,
            width=width,
            height=height,
            canonical_dpi=canonical_dpi,
        )
        encoded, buffer = cv2.imencode(".png", corrected)
        if not encoded:
            raise ValueError("Corrected template canvas could not be encoded")
        stored = self._storage.store_bytes(buffer.tobytes(), ".png", "corrected-images")
        evidence = EvidenceFile(
            file_id=stored.file_id,
            form_id=form_id,
            type=EvidenceType.CORRECTED_IMAGE,
            uri=stored.uri,
            sha256=stored.sha256,
        )
        try:
            self._evidence.add_evidence(evidence)
        except Exception:
            self._storage.delete_uri(stored.uri)
            raise
        self._audits.add_audit_event(
            AuditEvent(
                event_id=f"EVENT-{uuid4().hex}",
                form_id=form_id,
                event_type="NORMALIZE",
                actor_id="system",
                after={"file_id": evidence.file_id, "width": width, "height": height},
                evidence_ids=(evidence.file_id,),
            )
        )
        return evidence, corrected

    def record_template_field_crops(
        self, form_id: str, canonical_image: NDArray[Any], template: TemplateVersion
    ) -> dict[str, EvidenceFile]:
        """Create immutable crop evidence using the published template's normalized regions."""
        self._require_form(form_id)
        page = template.page
        regions = [
            FieldRegion(
                field.field_key,
                int(field.region.x * page.canonical_width_px),
                int(field.region.y * page.canonical_height_px),
                int(field.region.width * page.canonical_width_px),
                int(field.region.height * page.canonical_height_px),
            )
            for field in template.fields
        ]
        encoded_crops = self._pipeline.crop_fields(canonical_image, regions)
        evidence_by_key: dict[str, EvidenceFile] = {}
        for field_key, crop in encoded_crops.items():
            definition = next(item for item in template.fields if item.field_key == field_key)
            field_id = f"{form_id}:{template.version_id}:{field_key}"
            self._forms.add_form_field(
                FormField(
                    field_id=field_id,
                    form_id=form_id,
                    field_name=field_key,
                    source_region={
                        "x": int(definition.region.x * page.canonical_width_px),
                        "y": int(definition.region.y * page.canonical_height_px),
                        "width": int(definition.region.width * page.canonical_width_px),
                        "height": int(definition.region.height * page.canonical_height_px),
                    },
                )
            )
            encoded, buffer = cv2.imencode(".png", crop)
            if not encoded:
                raise ValueError(f"Field crop could not be encoded: {field_key}")
            stored = self._storage.store_bytes(buffer.tobytes(), ".png", "field-crops")
            evidence = EvidenceFile(
                file_id=stored.file_id,
                form_id=form_id,
                related_field_id=field_id,
                type=EvidenceType.FIELD_CROP,
                uri=stored.uri,
                sha256=stored.sha256,
            )
            try:
                self._evidence.add_evidence(evidence)
            except Exception:
                self._storage.delete_uri(stored.uri)
                raise
            evidence_by_key[field_key] = evidence
            candidate = self._recognize_template_crop(definition.recognition_engine, crop)
            if candidate is not None:
                self._recognition.add_recognition_attempt(
                    RecognitionAttempt(
                        attempt_id=f"ATTEMPT-{uuid4().hex}",
                        field_id=field_id,
                        engine=candidate.engine,
                        model_version=candidate.model_version,
                        candidate_value=candidate.value,
                        confidence=candidate.confidence,
                        crop_file_id=evidence.file_id,
                    )
                )
        self._audits.add_audit_event(
            AuditEvent(
                event_id=f"EVENT-{uuid4().hex}",
                form_id=form_id,
                event_type="CROP_FIELDS",
                actor_id="system",
                after={
                    "template_version_id": template.version_id,
                    "field_keys": list(evidence_by_key),
                },
                evidence_ids=tuple(item.file_id for item in evidence_by_key.values()),
            )
        )
        return evidence_by_key

    def _recognize_template_crop(
        self, recognition_engine: str, crop: NDArray[Any]
    ) -> RecognitionCandidate[Any] | None:
        if recognition_engine == "digit_template":
            return self._digits.recognize_cell(crop)
        if recognition_engine == "omr":
            return self._omr.recognize(crop)
        return None

    def record_candidate(
        self,
        form_id: str,
        field_id: str,
        crop: NDArray[Any],
        candidate: RecognitionCandidate[Any],
        actor_id: str,
    ) -> RecognitionAttempt:
        self._require_form(form_id)
        encoded, buffer = cv2.imencode(".png", crop)
        if not encoded:
            raise ValueError("Field crop could not be encoded")
        stored = self._storage.store_bytes(buffer.tobytes(), ".png", "field-crops")
        crop_evidence = EvidenceFile(
            file_id=stored.file_id,
            form_id=form_id,
            related_field_id=field_id,
            type=EvidenceType.FIELD_CROP,
            uri=stored.uri,
            sha256=stored.sha256,
        )
        self._evidence.add_evidence(crop_evidence)
        attempt = RecognitionAttempt(
            attempt_id=f"ATTEMPT-{uuid4().hex}",
            field_id=field_id,
            engine=candidate.engine,
            model_version=candidate.model_version,
            candidate_value=candidate.value,
            confidence=candidate.confidence,
            crop_file_id=crop_evidence.file_id,
        )
        self._recognition.add_recognition_attempt(attempt)
        self._audits.add_audit_event(
            AuditEvent(
                event_id=f"EVENT-{uuid4().hex}",
                form_id=form_id,
                event_type="RECOGNIZE",
                actor_id=actor_id,
                after={
                    "attempt_id": attempt.attempt_id,
                    "field_id": field_id,
                    "candidate": candidate.value,
                    "confidence": candidate.confidence,
                },
                evidence_ids=(crop_evidence.file_id,),
            )
        )
        return attempt

    def _require_form(self, form_id: str) -> Form:
        form = self._forms.get_form(form_id)
        if form is None:
            raise KeyError(f"Unknown form: {form_id}")
        return form

    def _audit_classification(
        self,
        before: Form,
        template_id: str,
        template_version: str,
        source: str,
        *,
        sheet_reference: str | None = None,
        job_profile_key: str | None = None,
        job_profile_version: str | None = None,
    ) -> None:
        self._audits.add_audit_event(
            AuditEvent(
                event_id=f"EVENT-{uuid4().hex}",
                form_id=before.form_id,
                event_type="CLASSIFY",
                actor_id="system",
                before={
                    "template_id": before.template_id,
                    "template_version": before.template_version,
                },
                after={
                    "template_id": template_id,
                    "template_version": template_version,
                    "source": source,
                    "sheet_reference": sheet_reference,
                    "job_profile_key": job_profile_key,
                    "job_profile_version": job_profile_version,
                },
            )
        )

    def _mark_classification_conflict(
        self,
        before: Form,
        references: tuple[str, ...],
    ) -> None:
        self._forms.set_review_status(before.form_id, ReviewStatus.NEEDS_CLASSIFICATION)
        self._audits.add_audit_event(
            AuditEvent(
                event_id=f"EVENT-{uuid4().hex}",
                form_id=before.form_id,
                event_type="CLASSIFICATION_CONFLICT",
                actor_id="system",
                before={
                    "template_id": before.template_id,
                    "template_version": before.template_version,
                },
                after={
                    "review_status": ReviewStatus.NEEDS_CLASSIFICATION.value,
                    "references": references,
                },
                reason="同一图片包含冲突的二维码身份，禁止自动猜测模板。",
            )
        )
