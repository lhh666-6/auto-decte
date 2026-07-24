"""Recognition / OCR module facade — RETIRED (Paper OCR removed)."""

from typing import Any

from numpy.typing import NDArray

from app.adapters.recognition.opencv import OpenCvImagePipeline, QualityAssessment


class RecognitionFacade:
    """DEPRECATED: Recognition / OCR module facade — retired with Paper OCR.

    Only image pipeline utilities (perspective correction, quality assessment)
    are preserved for non-OCR use by other modules.
    """

    def __init__(self, *, pipeline: OpenCvImagePipeline | None = None) -> None:
        self._pipeline = pipeline or OpenCvImagePipeline()

    def assess_quality(self, image: NDArray[Any]) -> QualityAssessment:
        return self._pipeline.assess_quality(image)

    def correct_perspective(
        self, image: NDArray[Any], corners: NDArray[Any],
        *, width: int, height: int,
    ) -> NDArray[Any]:
        return self._pipeline.correct_perspective(image, corners, width=width, height=height)
