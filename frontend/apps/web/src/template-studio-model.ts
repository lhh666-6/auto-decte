import type { TemplateRect } from "../../../packages/api-client/src/templates_ds";

export const QR_SAFE_ZONE: TemplateRect = { x: 0.8, y: 0.02, width: 0.16, height: 0.12 };

export function isProtectedOverlap(rect: TemplateRect, protectedRect: TemplateRect = QR_SAFE_ZONE): boolean {
  const candidate = normalizeRect(rect);
  const zone = normalizeRect(protectedRect);
  return candidate.x < zone.x + zone.width
    && candidate.x + candidate.width > zone.x
    && candidate.y < zone.y + zone.height
    && candidate.y + candidate.height > zone.y;
}

export function moveRect(
  rect: TemplateRect,
  deltaX: number,
  deltaY: number,
  protectedRect: TemplateRect = QR_SAFE_ZONE,
): TemplateRect {
  const current = normalizeRect(rect);
  const candidate = {
    ...current,
    x: clamp(current.x + deltaX, 0, 1 - current.width),
    y: clamp(current.y + deltaY, 0, 1 - current.height),
  };
  return isProtectedOverlap(candidate, protectedRect) ? rect : candidate;
}

export function resizeRect(
  rect: TemplateRect,
  width: number,
  height: number,
  protectedRect: TemplateRect = QR_SAFE_ZONE,
): TemplateRect {
  const current = normalizeRect(rect);
  const candidate = {
    ...current,
    width: clamp(width, 0, 1 - current.x),
    height: clamp(height, 0, 1 - current.y),
  };
  return isProtectedOverlap(candidate, protectedRect) ? rect : candidate;
}

export function canEdit(status: string): boolean {
  return status === "DRAFT";
}

function normalizeRect(rect: TemplateRect): TemplateRect {
  const x = clamp(rect.x, 0, 1);
  const y = clamp(rect.y, 0, 1);
  return {
    x,
    y,
    width: clamp(rect.width, 0, 1 - x),
    height: clamp(rect.height, 0, 1 - y),
  };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.round(Math.min(Math.max(value, minimum), maximum) * 1_000_000_000_000) / 1_000_000_000_000;
}
