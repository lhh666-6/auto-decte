import cv2
import numpy as np

from app.adapters.recognition.opencv import FieldRegion, OpenCvImagePipeline


def checkerboard(size: int = 240) -> np.ndarray:
    image = np.full((size, size, 3), 255, dtype=np.uint8)
    step = 20
    for row in range(0, size, step):
        for column in range(0, size, step):
            if (row // step + column // step) % 2 == 0:
                image[row : row + step, column : column + step] = 0
    return image


def test_quality_detection_rejects_blur_and_accepts_sharp_content() -> None:
    pipeline = OpenCvImagePipeline(min_laplacian_variance=100.0)
    sharp = checkerboard()
    blurred = cv2.GaussianBlur(sharp, (31, 31), 0)

    assert pipeline.assess_quality(sharp).acceptable is True
    assessment = pipeline.assess_quality(blurred)
    assert assessment.acceptable is False
    assert "BLURRY" in assessment.reason_codes


def test_qr_code_is_the_primary_template_identifier() -> None:
    qr = cv2.QRCodeEncoder_create().encode("TEMPLATE-A:1")
    pipeline = OpenCvImagePipeline()

    assert pipeline.read_template_qr(qr) == "TEMPLATE-A:1"


def test_perspective_correction_and_field_crop_have_requested_dimensions() -> None:
    image = checkerboard(300)
    corners = np.float32([[20, 30], [280, 10], [290, 290], [10, 270]])
    pipeline = OpenCvImagePipeline()

    corrected = pipeline.correct_perspective(image, corners, width=200, height=100)
    crops = pipeline.crop_fields(
        corrected,
        [FieldRegion("total_quantity", x=10, y=20, width=50, height=30)],
    )

    assert corrected.shape == (100, 200, 3)
    assert crops["total_quantity"].shape == (30, 50, 3)


def test_aruco_markers_restore_a_distorted_template_to_its_canonical_canvas() -> None:
    width, height = 600, 800
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    canvas[300:360, 200:280] = (255, 0, 0)
    marker_size, margin = 96, 24
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    for marker_id, left, top in (
        (10, margin, margin),
        (11, width - marker_size - margin, margin),
        (12, width - marker_size - margin, height - marker_size - margin),
        (13, margin, height - marker_size - margin),
    ):
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_size)
        canvas[top : top + marker_size, left : left + marker_size] = cv2.cvtColor(
            marker, cv2.COLOR_GRAY2BGR
        )
    source_corners = np.float32([[20, 50], [570, 25], [585, 765], [10, 785]])
    transform = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]),
        source_corners,
    )
    photographed = cv2.warpPerspective(canvas, transform, (600, 800))

    corrected = OpenCvImagePipeline().correct_template_perspective(
        photographed, width=width, height=height
    )

    assert corrected.shape == canvas.shape
    assert corrected[330, 240, 0] > 180
    assert corrected[330, 240, 1] < 50


def test_template_perspective_rejects_missing_directional_markers() -> None:
    with np.testing.assert_raises_regex(ValueError, "directional corner markers"):
        OpenCvImagePipeline().correct_template_perspective(
            np.full((300, 300, 3), 255, dtype=np.uint8), width=600, height=800
        )
