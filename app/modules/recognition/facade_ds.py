"""Recognition / OCR module facade."""

from typing import Any

from numpy.typing import NDArray

from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.recognition.candidate import RecognitionCandidate
from app.adapters.recognition.digits import DigitRecognizer
from app.adapters.recognition.omr import OmrRecognizer
from app.adapters.recognition.opencv import OpenCvImagePipeline, QualityAssessment
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.ports import AuditRepository
from app.application.recognize_forms import ClassificationResult, RecognizeForms
from app.domain.models import RecognitionAttempt


class RecognitionFacade:
    """Recognition / OCR module boundary backed by the classification and recognition service."""

    def __init__(
        self,
        repository: SqlAlchemyFormRepository,
        audits: AuditRepository,
        storage: LocalEvidenceStorage,
        pipeline: OpenCvImagePipeline | None = None,
        digit_recognizer: DigitRecognizer | None = None,
        omr_recognizer: OmrRecognizer | None = None,
    ) -> None:
        self._pipeline = pipeline or OpenCvImagePipeline()
        self._digit = digit_recognizer or DigitRecognizer()
        self._omr = omr_recognizer or OmrRecognizer()
        self._repository = repository
        self._recognizer = RecognizeForms(
            forms=repository,
            evidence=repository,
            audits=audits,
            storage=storage,
            pipeline=self._pipeline,
        )

    # --- Image pipeline ---

    def assess_quality(self, image: NDArray[Any]) -> QualityAssessment:
        """Assess whether an image is suitable for recognition."""
        return self._pipeline.assess_quality(image)

    def classify_image(self, form_id: str, image: NDArray[Any]) -> ClassificationResult:
        """Classify a form image by reading its QR code."""
        return self._recognizer.classify_image(form_id, image)

    def manual_reclassify(
        self,
        form_id: str,
        template_id: str,
        template_version: str,
        actor_id: str,
        reason: str,
    ) -> None:
        """Manually set the template classification for a form."""
        return self._recognizer.manual_reclassify(
            form_id, template_id, template_version, actor_id, reason
        )

    def correct_perspective(
        self,
        image: NDArray[Any],
        corners: NDArray[Any],
        *,
        width: int,
        height: int,
    ) -> NDArray[Any]:
        """Correct perspective distortion using four corner points."""
        return self._pipeline.correct_perspective(image, corners, width=width, height=height)

    # --- Field recognition ---

    def record_candidate(
        self,
        form_id: str,
        field_id: str,
        crop: NDArray[Any],
        candidate: RecognitionCandidate[Any],
        actor_id: str,
    ) -> RecognitionAttempt:
        """Persist a recognition candidate and its field crop as evidence."""
        return self._recognizer.record_candidate(form_id, field_id, crop, candidate, actor_id)

    def recognize_digit(self, image: NDArray[Any]) -> RecognitionCandidate[str]:
        """Recognise a single digit cell via template matching."""
        return self._digit.recognize_cell(image)

    def recognize_omr(self, image: NDArray[Any]) -> RecognitionCandidate[bool]:
        """Recognise a checkbox via fill-ratio OMR."""
        return self._omr.recognize(image)

    # --- Queries ---

    def list_recognition_attempts(self, field_id: str) -> list[RecognitionAttempt]:
        """List recognition attempts for a given field."""
        return self._repository.list_recognition_attempts(field_id)

    def list_recognition_attempts_for_form(self, form_id: str) -> list[RecognitionAttempt]:
        """List all recognition attempts for all fields of a form."""
        return self._repository.list_recognition_attempts_for_form(form_id)
