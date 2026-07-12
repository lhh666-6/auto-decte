"""Template management module facade."""

from typing import Any

from numpy.typing import NDArray

from app.adapters.recognition.opencv import FieldRegion, OpenCvImagePipeline


class TemplatesFacade:
    """Template management boundary backed by the image pipeline.

    Template definitions describe the expected layout of a form:
    which fields exist, where they are located on the image, and what
    coordinate system they use.
    """

    def __init__(
        self,
        pipeline: OpenCvImagePipeline | None = None,
    ) -> None:
        self._pipeline = pipeline or OpenCvImagePipeline()

    def crop_fields(
        self,
        image: NDArray[Any],
        regions: list[FieldRegion],
    ) -> dict[str, NDArray[Any]]:
        """Crop field regions from a form image according to a template layout."""
        return self._pipeline.crop_fields(image, regions)

    def read_template_qr(self, image: NDArray[Any]) -> str | None:
        """Decode a QR-code template reference from the image."""
        return self._pipeline.read_template_qr(image)
