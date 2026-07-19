"""Deterministic OpenCV image quality and geometry operations."""

from dataclasses import dataclass
from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    acceptable: bool
    reason_codes: tuple[str, ...]
    laplacian_variance: float
    dark_ratio: float
    bright_ratio: float


@dataclass(frozen=True, slots=True)
class FieldRegion:
    field_id: str
    x: int
    y: int
    width: int
    height: int


class OpenCvImagePipeline:
    def __init__(
        self,
        *,
        min_laplacian_variance: float = 60.0,
        max_dark_ratio: float = 0.95,
        max_bright_ratio: float = 0.98,
    ) -> None:
        self._min_laplacian_variance = min_laplacian_variance
        self._max_dark_ratio = max_dark_ratio
        self._max_bright_ratio = max_bright_ratio

    def assess_quality(self, image: Image) -> QualityAssessment:
        self._require_image(image)
        gray = self._gray(image)
        variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        dark_ratio = float(np.mean(gray < 20))
        bright_ratio = float(np.mean(gray > 245))
        reasons: list[str] = []
        if variance < self._min_laplacian_variance:
            reasons.append("BLURRY")
        if dark_ratio > self._max_dark_ratio:
            reasons.append("TOO_DARK")
        if bright_ratio > self._max_bright_ratio:
            reasons.append("GLARE_OR_BLANK")
        return QualityAssessment(
            acceptable=not reasons,
            reason_codes=tuple(reasons),
            laplacian_variance=variance,
            dark_ratio=dark_ratio,
            bright_ratio=bright_ratio,
        )

    def read_template_qr(self, image: Image) -> str | None:
        payloads = self.read_qr_payloads(image)
        return payloads[0] if payloads else None

    def read_qr_payloads(self, image: Image) -> tuple[str, ...]:
        """Decode every visible QR so callers can reject ambiguous paper identities."""
        self._require_image(image)
        candidate = image
        if min(image.shape[:2]) < 100:
            scale = max(4, 200 // min(image.shape[:2]))
            candidate = cast(
                Image,
                cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST),
            )
        height, width = candidate.shape[:2]
        regions = (
            candidate,
            candidate[
                int(height * 0.02) : int(height * 0.27),
                int(width * 0.70) : int(width * 0.95),
            ],
            candidate[
                int(height * 0.04) : int(height * 0.25),
                int(width * 0.75) : int(width * 0.93),
            ],
            candidate[
                int(height * 0.01) : int(height * 0.28),
                int(width * 0.45) : int(width * 0.80),
            ],
        )
        payloads: dict[str, None] = {}
        for region in regions:
            detector = cv2.QRCodeDetector()
            detected, values, _, _ = detector.detectAndDecodeMulti(region)
            if detected:
                payloads.update((value, None) for value in values if value)
            value, _, _ = detector.detectAndDecode(region)
            if value:
                payloads[value] = None
        return tuple(payloads)

    def correct_perspective(
        self,
        image: Image,
        corners: NDArray[np.float32],
        *,
        width: int,
        height: int,
    ) -> Image:
        self._require_image(image)
        source = np.asarray(corners, dtype=np.float32)
        if source.shape != (4, 2):
            raise ValueError("corners must contain top-left, top-right, bottom-right, bottom-left")
        target = np.asarray(
            [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
            dtype=np.float32,
        )
        transform = cv2.getPerspectiveTransform(source, target)
        return cast(Image, cv2.warpPerspective(image, transform, (width, height)))

    def correct_template_perspective(self, image: Image, *, width: int, height: int) -> Image:
        """Map a photographed template back to its canonical canvas via ArUco IDs 10--13."""
        self._require_image(image)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        corners, ids, _ = cv2.aruco.ArucoDetector(dictionary).detectMarkers(image)
        if ids is None:
            raise ValueError("all directional corner markers are required")
        observed = {
            int(marker_id): np.asarray(marker_corners, dtype=np.float32)
            .reshape(4, 2)
            .mean(axis=0)
            for marker_corners, marker_id in zip(corners, ids.flatten(), strict=True)
            if int(marker_id) in {10, 11, 12, 13}
        }
        if set(observed) != {10, 11, 12, 13}:
            raise ValueError("all directional corner markers are required")
        source = np.asarray([observed[marker_id] for marker_id in (10, 11, 12, 13)])
        target = self._canonical_marker_centres(width, height)
        transform = cv2.getPerspectiveTransform(source.astype(np.float32), target)
        return cast(Image, cv2.warpPerspective(image, transform, (width, height)))

    def crop_fields(self, image: Image, regions: list[FieldRegion]) -> dict[str, Image]:
        self._require_image(image)
        image_height, image_width = image.shape[:2]
        crops: dict[str, Image] = {}
        for region in regions:
            if (
                region.x < 0
                or region.y < 0
                or region.width <= 0
                or region.height <= 0
                or region.x + region.width > image_width
                or region.y + region.height > image_height
            ):
                raise ValueError(f"Field region outside image: {region.field_id}")
            crops[region.field_id] = image[
                region.y : region.y + region.height,
                region.x : region.x + region.width,
            ].copy()
        return crops

    @staticmethod
    def _gray(image: Image) -> Image:
        return image if image.ndim == 2 else cast(Image, cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))

    @staticmethod
    def _canonical_marker_centres(width: int, height: int) -> NDArray[np.float32]:
        marker_size = max(96, min(width, height) // 28)
        margin = max(24, marker_size // 5)
        half = marker_size / 2
        return np.asarray(
            [
                [margin + half, margin + half],
                [width - margin - half, margin + half],
                [width - margin - half, height - margin - half],
                [margin + half, height - margin - half],
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _require_image(image: Image) -> None:
        if image.size == 0 or image.ndim not in (2, 3):
            raise ValueError("A non-empty grayscale or BGR image is required")
