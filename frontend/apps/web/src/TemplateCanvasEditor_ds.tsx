import type {
  TemplateField,
  TemplateRect,
  TemplateVersion,
} from "@form-detection/api-client";
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import {
  PROTECTED_ZONES,
  PROTECTED_PLACEMENT_MESSAGE,
  QR_SAFE_ZONE,
  SHEET_CODE_SAFE_ZONE,
  moveRect,
  resizeRect,
} from "./template-studio-model";

type Props = {
  version: TemplateVersion;
  selectedFieldKey: string | null;
  editable: boolean;
  onSelect: (fieldKey: string) => void;
  onPersist: (field: TemplateField, region: TemplateRect) => Promise<void>;
  onReject: (reason: string) => void;
};

type Interaction = {
  pointerId: number;
  mode: "move" | "resize";
  field: TemplateField;
  startX: number;
  startY: number;
  startRegion: TemplateRect;
  latestRegion: TemplateRect;
  blocked: boolean;
};

export function TemplateCanvasEditor({
  version,
  selectedFieldKey,
  editable,
  onSelect,
  onPersist,
  onReject,
}: Props) {
  const paperRef = useRef<HTMLDivElement | null>(null);
  const interactionRef = useRef<Interaction | null>(null);
  const [previewRegions, setPreviewRegions] = useState<Record<string, TemplateRect>>({});

  useEffect(() => {
    setPreviewRegions(Object.fromEntries(version.fields.map((field) => [field.field_key, field.region])));
  }, [version]);

  function startInteraction(
    event: ReactPointerEvent<HTMLElement>,
    field: TemplateField,
    mode: Interaction["mode"],
  ) {
    if (!editable) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    onSelect(field.field_key);
    interactionRef.current = {
      pointerId: event.pointerId,
      mode,
      field,
      startX: event.clientX,
      startY: event.clientY,
      startRegion: previewRegions[field.field_key] ?? field.region,
      latestRegion: previewRegions[field.field_key] ?? field.region,
      blocked: false,
    };
  }

  function updateInteraction(event: ReactPointerEvent<HTMLElement>) {
    const interaction = interactionRef.current;
    const bounds = paperRef.current?.getBoundingClientRect();
    if (!interaction || !bounds || interaction.pointerId !== event.pointerId) return;
    const deltaX = (event.clientX - interaction.startX) / bounds.width;
    const deltaY = (event.clientY - interaction.startY) / bounds.height;
    const next = interaction.mode === "move"
      ? moveRect(interaction.startRegion, deltaX, deltaY, PROTECTED_ZONES)
      : resizeRect(
        interaction.startRegion,
        interaction.startRegion.width + deltaX,
        interaction.startRegion.height + deltaY,
        PROTECTED_ZONES,
      );
    interaction.blocked = next === interaction.startRegion && (deltaX !== 0 || deltaY !== 0);
    interaction.latestRegion = next;
    setPreviewRegions((current) => ({ ...current, [interaction.field.field_key]: next }));
  }

  function finishInteraction(event: ReactPointerEvent<HTMLElement>, cancelled = false) {
    const interaction = interactionRef.current;
    if (!interaction || interaction.pointerId !== event.pointerId) return;
    interactionRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    const next = interaction.latestRegion;
    if (cancelled || interaction.blocked) {
      setPreviewRegions((current) => ({
        ...current,
        [interaction.field.field_key]: interaction.startRegion,
      }));
      if (interaction.blocked) onReject(PROTECTED_PLACEMENT_MESSAGE);
      return;
    }
    if (!sameRect(next, interaction.startRegion)) {
      void persistOrRestore(interaction.field, next, interaction.startRegion);
    }
  }

  async function persistOrRestore(
    field: TemplateField,
    next: TemplateRect,
    previous: TemplateRect,
  ) {
    try {
      await onPersist(field, next);
    } catch {
      setPreviewRegions((current) => ({ ...current, [field.field_key]: previous }));
    }
  }

  function handleKeyboard(field: TemplateField, event: React.KeyboardEvent<HTMLButtonElement>) {
    if (!editable || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      return;
    }
    event.preventDefault();
    const current = previewRegions[field.field_key] ?? field.region;
    const step = event.shiftKey ? 0.01 : 0.005;
    const horizontal = event.key === "ArrowLeft" ? -step : event.key === "ArrowRight" ? step : 0;
    const vertical = event.key === "ArrowUp" ? -step : event.key === "ArrowDown" ? step : 0;
    const next = event.altKey
      ? resizeRect(current, current.width + horizontal, current.height + vertical, PROTECTED_ZONES)
      : moveRect(current, horizontal, vertical, PROTECTED_ZONES);
    if (next === current) {
      onReject(PROTECTED_PLACEMENT_MESSAGE);
      return;
    }
    setPreviewRegions((regions) => ({ ...regions, [field.field_key]: next }));
    void persistOrRestore(field, next, current);
  }

  return (
    <section className="studio-canvas" aria-label="模板字段画布">
      <div className="canvas-toolbar">
        <div><span className="eyebrow">标准画布</span><strong>{version.page.size} · V{version.version}</strong></div>
        <span>{editable ? "拖动字段；右下角缩放；Alt+方向键调整大小" : "当前版本只读"}</span>
      </div>
      <div
        ref={paperRef}
        className={`paper-preview template-canvas-paper ${editable ? "editable" : "read-only"}`}
        style={{ aspectRatio: `${version.page.width_mm} / ${version.page.height_mm}` }}
      >
        <div className="printable-boundary" aria-hidden="true" />
        <span className="marker top-left">10</span>
        <span className="marker top-right">11</span>
        <span className="marker bottom-left">13</span>
        <span className="marker bottom-right">12</span>
        <ProtectedZone label="模板 QR" region={QR_SAFE_ZONE} className="qr-zone" />
        <ProtectedZone label="纸张实例码" region={SHEET_CODE_SAFE_ZONE} className="sheet-zone" />
        {version.fields.map((field) => {
          const region = previewRegions[field.field_key] ?? field.region;
          return (
            <button
              key={field.field_key}
              type="button"
              className={`template-field-overlay ${field.field_key === selectedFieldKey ? "selected" : ""}`}
              style={rectStyle(region)}
              aria-label={`选择字段 ${field.display_name}`}
              aria-pressed={field.field_key === selectedFieldKey}
              onClick={() => onSelect(field.field_key)}
              onKeyDown={(event) => handleKeyboard(field, event)}
              onPointerDown={(event) => startInteraction(event, field, "move")}
              onPointerMove={updateInteraction}
              onPointerUp={finishInteraction}
              onPointerCancel={(event) => finishInteraction(event, true)}
            >
              <span>{field.display_name}</span>
              <small>{field.field_key}</small>
              {editable && (
                <span
                  className="resize-handle"
                  aria-hidden="true"
                  onPointerDown={(event) => startInteraction(event, field, "resize")}
                  onPointerMove={updateInteraction}
                  onPointerUp={finishInteraction}
                  onPointerCancel={(event) => finishInteraction(event, true)}
                />
              )}
            </button>
          );
        })}
        {version.fields.length === 0 && (
          <div className="empty-template-canvas">从左侧加入字段后，可在此选择和调整位置。</div>
        )}
      </div>
    </section>
  );
}

function ProtectedZone({
  label,
  region,
  className,
}: {
  label: string;
  region: TemplateRect;
  className: string;
}) {
  return <div className={`protected-zone ${className}`} style={rectStyle(region)}>{label}</div>;
}

function rectStyle(region: TemplateRect): React.CSSProperties {
  return {
    left: `${region.x * 100}%`,
    top: `${region.y * 100}%`,
    width: `${region.width * 100}%`,
    height: `${region.height * 100}%`,
  };
}

function sameRect(left: TemplateRect, right: TemplateRect): boolean {
  return left.x === right.x
    && left.y === right.y
    && left.width === right.width
    && left.height === right.height;
}
