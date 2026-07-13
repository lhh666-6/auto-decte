"""Deterministic print artifacts for published paper-form templates."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.domain.templates_ds import (
    TemplateArtifact,
    TemplateVersion,
    build_sheet_payload,
    build_template_payload,
)


class TemplatePrintRenderer:
    """Render printable PNG/PDF files without exposing their paths to clients."""

    def __init__(self, artifact_root: Path) -> None:
        self._artifact_root = artifact_root

    def sheet_payload(self, print_batch: str, sequence: int) -> str:
        return build_sheet_payload(print_batch, sequence)

    def render(
        self,
        version: TemplateVersion,
        *,
        print_batch: str | None = None,
        sequence: int | None = None,
    ) -> tuple[TemplateArtifact, TemplateArtifact]:
        if version.status.value != "PUBLISHED":
            raise ValueError("only published template versions can be rendered")
        if (print_batch is None) != (sequence is None):
            raise ValueError("print_batch and sequence must be supplied together")

        payload = build_template_payload(version.template_key, version.version)
        sheet_payload = (
            self.sheet_payload(print_batch, sequence)
            if print_batch is not None and sequence is not None
            else None
        )
        image = self._render_canvas(version, payload, sheet_payload)
        output_dir = self._artifact_root / "template-artifacts" / version.template_key
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = ""
        if print_batch is not None and sequence is not None:
            suffix = f"-{print_batch}-{sequence:06d}"
        base_name = f"{version.template_key}-v{version.version}{suffix}"
        png_path = output_dir / f"{base_name}.png"
        pdf_path = output_dir / f"{base_name}.pdf"
        image.save(png_path, format="PNG", dpi=(version.page.canonical_dpi,) * 2)
        image.convert("RGB").save(
            pdf_path,
            format="PDF",
            resolution=float(version.page.canonical_dpi),
        )
        return (
            self._artifact(version.version_id, "PRINT_PNG", png_path),
            self._artifact(version.version_id, "PRINT_PDF", pdf_path),
        )

    def _render_canvas(
        self,
        version: TemplateVersion,
        template_payload: str,
        sheet_payload: str | None,
    ) -> Image.Image:
        page = version.page
        image = Image.new("RGB", (page.canonical_width_px, page.canonical_height_px), "white")
        draw = ImageDraw.Draw(image)
        draw.text((96, 96), f"{version.template_key} / V{version.version}", fill="black")
        self._paste_qr(image, template_payload, 0.80, 0.02, 0.16, 0.12)
        if sheet_payload is not None:
            self._paste_qr(image, sheet_payload, 0.62, 0.02, 0.14, 0.12)
        self._draw_corner_markers(image)
        for field in version.fields:
            left = int(field.region.x * page.canonical_width_px)
            top = int(field.region.y * page.canonical_height_px)
            right = int((field.region.x + field.region.width) * page.canonical_width_px)
            bottom = int((field.region.y + field.region.height) * page.canonical_height_px)
            draw.rectangle((left, top, right, bottom), outline="black", width=2)
            draw.text((left + 4, top + 4), field.field_key, fill="black")
        return image

    @staticmethod
    def _paste_qr(
        image: Image.Image,
        payload: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        opencv_module: Any = cv2
        encoder = opencv_module.QRCodeEncoder_create()
        matrix = encoder.encode(payload)
        qr = Image.fromarray(np.where(matrix == 0, 0, 255).astype(np.uint8), mode="L")
        page_width, page_height = image.size
        target = (int(width * page_width), int(height * page_height))
        qr = qr.resize(target, Image.Resampling.NEAREST).convert("RGB")
        image.paste(qr, (int(x * page_width), int(y * page_height)))

    @staticmethod
    def _draw_corner_markers(image: Image.Image) -> None:
        width, height = image.size
        marker_size = max(96, min(width, height) // 28)
        margin = max(24, marker_size // 5)
        locations = (
            (10, margin, margin),
            (11, width - marker_size - margin, margin),
            (12, width - marker_size - margin, height - marker_size - margin),
            (13, margin, height - marker_size - margin),
        )
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        for marker_id, left, top in locations:
            marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_size)
            image.paste(Image.fromarray(marker, mode="L").convert("RGB"), (left, top))

    @staticmethod
    def _artifact(version_id: str, kind: str, path: Path) -> TemplateArtifact:
        return TemplateArtifact(
            artifact_id=f"TART-{uuid4().hex}",
            version_id=version_id,
            kind=kind,
            download_name=path.name,
            internal_uri=str(path.resolve()),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
