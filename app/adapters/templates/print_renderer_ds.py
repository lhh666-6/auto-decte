"""Deterministic 300-DPI print artifacts for published Chinese paper templates."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.domain.templates_ds import (
    ElementKind,
    FieldDefinition,
    PageSpec,
    PaperEntryMode,
    Rect,
    StaticElement,
    TemplateArtifact,
    TemplateVersion,
    build_sheet_payload,
    build_template_payload,
)

_OUTER_MARGIN_MM = 5.0
_QR_SIZE_MM = 29.0
_QR_SYMBOL_MM = 18.0
_QR_GAP_MM = 5.0
_MARKER_SIZE_MM = 12.0


class ChineseFontUnavailable(RuntimeError):
    """No configured font can render the reviewed Chinese paper forms."""


class TemplatePrintRenderer:
    """Render single-form and imposed payroll artifacts without exposing storage paths."""

    def __init__(
        self,
        artifact_root: Path,
        *,
        font_candidates: Sequence[Path] | None = None,
    ) -> None:
        self._artifact_root = artifact_root
        self._font_candidates = (
            tuple(font_candidates) if font_candidates is not None else _default_font_candidates()
        )
        self._resolved_font_path: Path | None = None

    def sheet_payload(self, print_batch: str, sequence: int) -> str:
        return build_sheet_payload(print_batch, sequence)

    def validate_print_support(self) -> Path:
        """Resolve and load the required CJK font before publication changes state."""
        if self._resolved_font_path is not None:
            return self._resolved_font_path
        failures: list[str] = []
        for candidate in self._font_candidates:
            if not candidate.is_file():
                continue
            try:
                ImageFont.truetype(str(candidate), size=32)
            except OSError as error:
                failures.append(f"{candidate}: {error}")
                continue
            self._resolved_font_path = candidate
            return candidate
        detail = f" Tried: {', '.join(failures)}" if failures else ""
        raise ChineseFontUnavailable(
            "未找到可用中文字体，不能发布或生成工资表；请安装微软雅黑、思源黑体或 Noto Sans CJK。"
            + detail
        )

    def render(
        self,
        version: TemplateVersion,
        *,
        print_batch: str | None = None,
        sequence: int | None = None,
    ) -> tuple[TemplateArtifact, ...]:
        if version.status.value != "PUBLISHED":
            raise ValueError("only published template versions can be rendered")
        if (print_batch is None) != (sequence is None):
            raise ValueError("print_batch and sequence must be supplied together")
        self.validate_print_support()

        payload = build_template_payload(version.template_key, version.version)
        sheet_payload = (
            self.sheet_payload(print_batch, sequence)
            if print_batch is not None and sequence is not None
            else None
        )
        image = self._render_canvas(version, payload, sheet_payload)
        output_dir = self._artifact_root / "template-artifacts" / version.template_key
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = _instance_suffix(print_batch, sequence)
        base_name = f"{version.template_key}-v{version.version}{suffix}"
        png_path = output_dir / f"{base_name}.png"
        pdf_path = output_dir / f"{base_name}.pdf"
        image.save(png_path, format="PNG", dpi=(version.page.canonical_dpi,) * 2)
        _save_pdf(image, pdf_path, version.page.canonical_dpi)
        artifacts = [
            self._artifact(version.version_id, "PRINT_PNG", png_path),
            self._artifact(version.version_id, "PRINT_PDF", pdf_path),
        ]

        if version.print_imposition is not None:
            imposed = self.compose_imposition(
                version,
                print_batch=print_batch,
                first_sequence=sequence,
            )
            imposed_path = output_dir / f"{base_name}-imposed.pdf"
            _save_pdf(imposed, imposed_path, version.print_imposition.carrier.canonical_dpi)
            artifacts.append(self._artifact(version.version_id, "PRINT_IMPOSED_PDF", imposed_path))
        return tuple(artifacts)

    def compose_imposition(
        self,
        version: TemplateVersion,
        *,
        print_batch: str | None = None,
        first_sequence: int | None = None,
    ) -> Image.Image:
        """Compose independent form instances on the configured carrier for preview/PDF."""
        if version.print_imposition is None:
            raise ValueError("template has no print imposition")
        if (print_batch is None) != (first_sequence is None):
            raise ValueError("print_batch and first_sequence must be supplied together")
        self.validate_print_support()
        imposition = version.print_imposition
        carrier = imposition.carrier
        canvas = Image.new(
            "RGB",
            (carrier.canonical_width_px, carrier.canonical_height_px),
            "white",
        )
        template_payload = build_template_payload(version.template_key, version.version)
        scale_x = carrier.canonical_width_px / carrier.width_mm
        scale_y = carrier.canonical_height_px / carrier.height_mm
        cell_width = round(imposition.cell_width_mm * scale_x)
        cell_height = round(imposition.cell_height_mm * scale_y)
        gap_x = round(imposition.horizontal_gap_mm * scale_x)
        gap_y = round(imposition.vertical_gap_mm * scale_y)
        margin_x = round(imposition.margin_mm * scale_x)
        margin_y = round(imposition.margin_mm * scale_y)
        form_width = round(version.page.width_mm * scale_x)
        form_height = round(version.page.height_mm * scale_y)

        for slot in range(imposition.slot_count):
            row, column = divmod(slot, imposition.columns)
            sheet_payload = None
            if print_batch is not None and first_sequence is not None:
                sheet_payload = self.sheet_payload(print_batch, first_sequence + slot)
            form = self._render_canvas(version, template_payload, sheet_payload)
            if form.size != (form_width, form_height):
                form = form.resize((form_width, form_height), Image.Resampling.LANCZOS)
            cell_left = margin_x + column * (cell_width + gap_x)
            cell_top = margin_y + row * (cell_height + gap_y)
            left = cell_left + max(0, (cell_width - form_width) // 2)
            top = cell_top + max(0, (cell_height - form_height) // 2)
            canvas.paste(form, (left, top))

        if imposition.include_cut_lines:
            self._draw_imposition_cut_lines(canvas, version)
        return canvas

    def _render_canvas(
        self,
        version: TemplateVersion,
        template_payload: str,
        sheet_payload: str | None,
    ) -> Image.Image:
        page = version.page
        image = Image.new(
            "RGB",
            (page.canonical_width_px, page.canonical_height_px),
            "white",
        )
        draw = ImageDraw.Draw(image)
        if version.static_elements:
            for element in version.static_elements:
                self._draw_static_element(draw, element, page)
        else:
            self._draw_legacy_header(draw, version)
        printed_checkboxes = tuple(
            element.region
            for element in version.static_elements
            if element.kind is ElementKind.CHECKBOX
        )
        for field in version.fields:
            self._draw_field(draw, field, page, printed_checkboxes)
        self._paste_identity_qrs(image, page, template_payload, sheet_payload)
        self._draw_corner_markers(image, page)
        return image

    def _draw_static_element(
        self,
        draw: ImageDraw.ImageDraw,
        element: StaticElement,
        page: PageSpec,
    ) -> None:
        box = _pixel_rect(element.region, page)
        if element.kind is ElementKind.TITLE:
            self._draw_fitted_text(draw, box, element.text, maximum_px=_mm_to_px(6.0, page))
        elif element.kind is ElementKind.LABEL:
            self._draw_fitted_text(
                draw,
                box,
                element.text,
                maximum_px=_mm_to_px(3.0, page),
                align="left",
            )
        elif element.kind is ElementKind.ROLE_SECTION:
            draw.rectangle(box, fill="#e8edf2", outline="black", width=_stroke(page))
            self._draw_fitted_text(
                draw,
                box,
                element.text,
                maximum_px=_mm_to_px(3.2, page),
                align="left",
            )
        elif element.kind is ElementKind.TABLE_GRID:
            self._draw_grid(draw, box, page)
        elif element.kind is ElementKind.CHECKBOX:
            draw.rectangle(box, outline="black", width=_stroke(page))
        elif element.kind is ElementKind.SIGNATURE_LINE:
            draw.line((box[0], box[3], box[2], box[3]), fill="black", width=_stroke(page))
        elif element.kind is ElementKind.CUT_LINE:
            _draw_dashed_line(draw, (box[0], box[1]), (box[2], box[3]), _stroke(page))
        elif element.kind is ElementKind.LINE:
            draw.line((box[0], box[1], box[2], box[3]), fill="black", width=_stroke(page))
        elif element.kind is ElementKind.BOX:
            draw.rectangle(box, outline="black", width=_stroke(page))

    def _draw_field(
        self,
        draw: ImageDraw.ImageDraw,
        field: FieldDefinition,
        page: PageSpec,
        printed_checkboxes: tuple[Rect, ...],
    ) -> None:
        box = _pixel_rect(field.region, page)
        stroke = _stroke(page)
        mode = field.paper_entry_mode
        if mode is PaperEntryMode.CHECKBOX:
            printed = next(
                (region for region in printed_checkboxes if _overlaps(region, field.region)),
                None,
            )
            if printed is not None:
                check_box = _pixel_rect(printed, page)
            else:
                side = min(box[3] - box[1], _mm_to_px(5.0, page))
                check_box = (box[0], box[1], box[0] + side, box[1] + side)
                draw.rectangle(check_box, outline="black", width=stroke)
            label_box = (check_box[2] + stroke * 2, box[1], box[2], box[3])
            self._draw_fitted_text(
                draw,
                label_box,
                field.display_name,
                maximum_px=_mm_to_px(3.0, page),
                align="left",
            )
            return
        if mode is PaperEntryMode.SIGNATURE:
            self._draw_fitted_text(
                draw,
                box,
                field.display_name,
                maximum_px=_mm_to_px(3.0, page),
                align="left",
            )
            draw.line((box[0], box[3], box[2], box[3]), fill="black", width=stroke)
            return
        if mode is PaperEntryMode.DIGIT_BOXES:
            label_height = max(stroke * 3, round((box[3] - box[1]) * 0.38))
            label_box = (box[0], box[1], box[2], box[1] + label_height)
            self._draw_fitted_text(
                draw,
                label_box,
                field.display_name,
                maximum_px=_mm_to_px(2.8, page),
                align="left",
            )
            digit_top = label_box[3]
            digit_count = 6
            digit_width = max(1, (box[2] - box[0]) // digit_count)
            for index in range(digit_count):
                left = box[0] + index * digit_width
                right = box[2] if index == digit_count - 1 else left + digit_width
                draw.rectangle((left, digit_top, right, box[3]), outline="black", width=stroke)
            return
        draw.rectangle(box, outline="black", width=stroke)
        self._draw_fitted_text(
            draw,
            box,
            field.display_name,
            maximum_px=_mm_to_px(3.0, page),
            align="left",
        )

    def _draw_legacy_header(
        self,
        draw: ImageDraw.ImageDraw,
        version: TemplateVersion,
    ) -> None:
        page = version.page
        box = (
            _mm_to_px(18.0, page, horizontal=True),
            _mm_to_px(5.0, page),
            round(page.canonical_width_px * 0.52),
            _mm_to_px(15.0, page),
        )
        self._draw_fitted_text(
            draw,
            box,
            f"{version.template_key} / V{version.version}",
            maximum_px=_mm_to_px(4.0, page),
            align="left",
        )

    def _draw_grid(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        page: PageSpec,
    ) -> None:
        stroke = _stroke(page)
        draw.rectangle(box, outline="black", width=stroke)

    def _draw_fitted_text(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        text: str,
        *,
        maximum_px: int | None = None,
        align: str = "center",
    ) -> None:
        width = max(1, box[2] - box[0])
        height = max(1, box[3] - box[1])
        size = max(8, min(maximum_px or height, height))
        font = self._font(size)
        while size > 8:
            bounds = draw.textbbox((0, 0), text, font=font)
            if bounds[2] - bounds[0] <= width - 6 and bounds[3] - bounds[1] <= height - 4:
                break
            size -= 1
            font = self._font(size)
        bounds = draw.textbbox((0, 0), text, font=font)
        text_width = bounds[2] - bounds[0]
        text_height = bounds[3] - bounds[1]
        left = box[0] + 3 if align == "left" else box[0] + max(0, (width - text_width) // 2)
        top = box[1] + max(0, (height - text_height) // 2) - bounds[1]
        draw.text((left, top), text, fill="black", font=font)

    def _font(self, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(str(self.validate_print_support()), size=max(8, size))

    @staticmethod
    def _paste_identity_qrs(
        image: Image.Image,
        page: PageSpec,
        template_payload: str,
        sheet_payload: str | None,
    ) -> None:
        edge_x = _OUTER_MARGIN_MM / page.width_mm
        edge_y = _OUTER_MARGIN_MM / page.height_mm
        qr_safe_width = _QR_SIZE_MM / page.width_mm
        qr_safe_height = _QR_SIZE_MM / page.height_mm
        qr_width = _QR_SYMBOL_MM / page.width_mm
        qr_height = _QR_SYMBOL_MM / page.height_mm
        template_safe_x = 1 - edge_x - qr_safe_width
        qr_y = edge_y + qr_safe_height - qr_height
        TemplatePrintRenderer._paste_qr(
            image,
            template_payload,
            template_safe_x,
            qr_y,
            qr_width,
            qr_height,
        )
        if sheet_payload is not None:
            sheet_safe_x = template_safe_x - _QR_GAP_MM / page.width_mm - qr_safe_width
            TemplatePrintRenderer._paste_qr(
                image,
                sheet_payload,
                sheet_safe_x,
                qr_y,
                qr_width,
                qr_height,
            )

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
        matrix = np.pad(matrix, 4, mode="constant", constant_values=255)
        qr = Image.fromarray(np.where(matrix == 0, 0, 255).astype(np.uint8), mode="L")
        page_width, page_height = image.size
        target = (round(width * page_width), round(height * page_height))
        qr = qr.resize(target, Image.Resampling.NEAREST).convert("RGB")
        image.paste(qr, (round(x * page_width), round(y * page_height)))

    @staticmethod
    def _draw_corner_markers(image: Image.Image, page: PageSpec) -> None:
        marker_width = _mm_to_px(_MARKER_SIZE_MM, page, horizontal=True)
        marker_height = _mm_to_px(_MARKER_SIZE_MM, page)
        marker_size = min(marker_width, marker_height)
        margin_x = _mm_to_px(_OUTER_MARGIN_MM, page, horizontal=True)
        margin_y = _mm_to_px(_OUTER_MARGIN_MM, page)
        width, height = image.size
        locations = (
            (10, margin_x, margin_y),
            (11, width - marker_size - margin_x, margin_y),
            (12, width - marker_size - margin_x, height - marker_size - margin_y),
            (13, margin_x, height - marker_size - margin_y),
        )
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        for marker_id, left, top in locations:
            marker = cv2.aruco.generateImageMarker(dictionary, marker_id, marker_size)
            image.paste(Image.fromarray(marker, mode="L").convert("RGB"), (left, top))

    @staticmethod
    def _draw_imposition_cut_lines(image: Image.Image, version: TemplateVersion) -> None:
        imposition = version.print_imposition
        if imposition is None:
            return
        draw = ImageDraw.Draw(image)
        carrier = imposition.carrier
        scale_x = carrier.canonical_width_px / carrier.width_mm
        scale_y = carrier.canonical_height_px / carrier.height_mm
        stroke = max(1, round(carrier.canonical_dpi / 150))
        for column in range(1, imposition.columns):
            boundary_mm = (
                imposition.margin_mm
                + column * imposition.cell_width_mm
                + (column - 0.5) * imposition.horizontal_gap_mm
            )
            x = round(boundary_mm * scale_x)
            _draw_dashed_line(draw, (x, 0), (x, image.height), stroke)
        for row in range(1, imposition.rows):
            boundary_mm = (
                imposition.margin_mm
                + row * imposition.cell_height_mm
                + (row - 0.5) * imposition.vertical_gap_mm
            )
            y = round(boundary_mm * scale_y)
            _draw_dashed_line(draw, (0, y), (image.width, y), stroke)

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


def _default_font_candidates() -> tuple[Path, ...]:
    configured = os.getenv("FORM_DEMO_CJK_FONT_PATH")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        Path(value)
        for value in (
            r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        )
    )
    return tuple(candidates)


def _instance_suffix(print_batch: str | None, sequence: int | None) -> str:
    if print_batch is None or sequence is None:
        return ""
    return f"-{print_batch}-{sequence:06d}"


def _pixel_rect(region: Rect, page: PageSpec) -> tuple[int, int, int, int]:
    return (
        round(region.x * page.canonical_width_px),
        round(region.y * page.canonical_height_px),
        round((region.x + region.width) * page.canonical_width_px),
        round((region.y + region.height) * page.canonical_height_px),
    )


def _overlaps(left: Rect, right: Rect) -> bool:
    return (
        left.x < right.x + right.width
        and left.x + left.width > right.x
        and left.y < right.y + right.height
        and left.y + left.height > right.y
    )


def _mm_to_px(value: float, page: PageSpec, *, horizontal: bool = False) -> int:
    if horizontal:
        return max(1, round(value / page.width_mm * page.canonical_width_px))
    return max(1, round(value / page.height_mm * page.canonical_height_px))


def _stroke(page: PageSpec) -> int:
    return max(1, round(page.canonical_dpi / 150))


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    width: int,
) -> None:
    dash = max(8, width * 5)
    if start[0] == end[0]:
        for top in range(start[1], end[1], dash * 2):
            draw.line((start[0], top, end[0], min(top + dash, end[1])), fill="black", width=width)
        return
    for left in range(start[0], end[0], dash * 2):
        draw.line((left, start[1], min(left + dash, end[0]), end[1]), fill="black", width=width)


def _save_pdf(image: Image.Image, path: Path, dpi: int) -> None:
    image.convert("RGB").save(path, format="PDF", resolution=float(dpi))
