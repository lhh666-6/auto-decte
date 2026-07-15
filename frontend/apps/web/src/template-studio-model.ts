import type { TemplateRect } from "../../../packages/api-client/src/templates_ds";

export const QR_SAFE_ZONE: TemplateRect = { x: 0.78, y: 0.02, width: 0.16, height: 0.12 };
export const SHEET_CODE_SAFE_ZONE: TemplateRect = { x: 0.62, y: 0.02, width: 0.14, height: 0.12 };
export const PROTECTED_PLACEMENT_MESSAGE = "该位置属于二维码、实例码、定位标记或打印安全区，不能放置字段。";

const PAGE_EDGE = 0.025;
const CORNER_MARKER = 0.07;

export const PROTECTED_ZONES: readonly TemplateRect[] = [
  QR_SAFE_ZONE,
  SHEET_CODE_SAFE_ZONE,
  { x: 0, y: 0, width: 1, height: PAGE_EDGE },
  { x: 0, y: 1 - PAGE_EDGE, width: 1, height: PAGE_EDGE },
  { x: 0, y: 0, width: PAGE_EDGE, height: 1 },
  { x: 1 - PAGE_EDGE, y: 0, width: PAGE_EDGE, height: 1 },
  { x: 0, y: 0, width: CORNER_MARKER, height: CORNER_MARKER },
  { x: 1 - CORNER_MARKER, y: 0, width: CORNER_MARKER, height: CORNER_MARKER },
  { x: 0, y: 1 - CORNER_MARKER, width: CORNER_MARKER, height: CORNER_MARKER },
  {
    x: 1 - CORNER_MARKER,
    y: 1 - CORNER_MARKER,
    width: CORNER_MARKER,
    height: CORNER_MARKER,
  },
];

type ProtectedRegion = TemplateRect | readonly TemplateRect[];

export function isProtectedOverlap(
  rect: TemplateRect,
  protectedRegion: ProtectedRegion = PROTECTED_ZONES,
): boolean {
  const candidate = normalizeRect(rect);
  const zones = Array.isArray(protectedRegion) ? protectedRegion : [protectedRegion];
  return zones.some((item) => {
    const zone = normalizeRect(item);
    return candidate.x < zone.x + zone.width
      && candidate.x + candidate.width > zone.x
      && candidate.y < zone.y + zone.height
      && candidate.y + candidate.height > zone.y;
  });
}

export function moveRect(
  rect: TemplateRect,
  deltaX: number,
  deltaY: number,
  protectedRegion: ProtectedRegion = PROTECTED_ZONES,
): TemplateRect {
  const current = normalizeRect(rect);
  const candidate = {
    ...current,
    x: clamp(current.x + deltaX, 0, 1 - current.width),
    y: clamp(current.y + deltaY, 0, 1 - current.height),
  };
  return isProtectedOverlap(candidate, protectedRegion) ? rect : candidate;
}

export function resizeRect(
  rect: TemplateRect,
  width: number,
  height: number,
  protectedRegion: ProtectedRegion = PROTECTED_ZONES,
): TemplateRect {
  const current = normalizeRect(rect);
  const candidate = {
    ...current,
    width: clamp(width, 0, 1 - current.x),
    height: clamp(height, 0, 1 - current.y),
  };
  return isProtectedOverlap(candidate, protectedRegion) ? rect : candidate;
}

export function canEdit(status: string): boolean {
  return status === "DRAFT" || status === "PREFLIGHT_FAILED" || status === "READY_TO_PUBLISH";
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
