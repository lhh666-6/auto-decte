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
  alignRect,
  type Alignment,
  isProtectedOverlap,
  moveRect,
  rectInMillimeters,
  resizeRect,
  snapRectToMillimeters,
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

type GeometryChange = {
  field: TemplateField;
  before: TemplateRect;
  after: TemplateRect;
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
  const [past, setPast] = useState<GeometryChange[]>([]);
  const [future, setFuture] = useState<GeometryChange[]>([]);
  const [historyWorking, setHistoryWorking] = useState(false);
  const [gridSnap, setGridSnap] = useState(true);
  const [zoom, setZoom] = useState(1);

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
    const rawNext = interaction.mode === "move"
      ? moveRect(interaction.startRegion, deltaX, deltaY, PROTECTED_ZONES)
      : resizeRect(
        interaction.startRegion,
        interaction.startRegion.width + deltaX,
        interaction.startRegion.height + deltaY,
        PROTECTED_ZONES,
      );
    const snapped = gridSnap ? snapRectToMillimeters(rawNext, version.page) : rawNext;
    const next = isProtectedOverlap(snapped, PROTECTED_ZONES) ? interaction.startRegion : snapped;
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
      void persistOrRestore(interaction.field, next, interaction.startRegion, true);
    }
  }

  async function persistOrRestore(
    field: TemplateField,
    next: TemplateRect,
    previous: TemplateRect,
    recordHistory = false,
  ) {
    try {
      await onPersist(field, next);
      if (recordHistory) {
        setPast((items) => [...items, { field, before: previous, after: next }]);
        setFuture([]);
      }
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
    const stepMm = event.shiftKey ? 5 : 1;
    const horizontal = event.key === "ArrowLeft" ? -stepMm / version.page.width_mm : event.key === "ArrowRight" ? stepMm / version.page.width_mm : 0;
    const vertical = event.key === "ArrowUp" ? -stepMm / version.page.height_mm : event.key === "ArrowDown" ? stepMm / version.page.height_mm : 0;
    const rawNext = event.altKey
      ? resizeRect(current, current.width + horizontal, current.height + vertical, PROTECTED_ZONES)
      : moveRect(current, horizontal, vertical, PROTECTED_ZONES);
    const next = gridSnap ? snapRectToMillimeters(rawNext, version.page) : rawNext;
    if (next === current) {
      onReject(PROTECTED_PLACEMENT_MESSAGE);
      return;
    }
    setPreviewRegions((regions) => ({ ...regions, [field.field_key]: next }));
    void persistOrRestore(field, next, current, true);
  }

  async function undo() {
    const change = past.at(-1);
    if (!change || historyWorking) return;
    setHistoryWorking(true);
    setPreviewRegions((regions) => ({ ...regions, [change.field.field_key]: change.before }));
    try {
      await onPersist(currentField(change.field), change.before);
      setPast((items) => items.slice(0, -1));
      setFuture((items) => [...items, change]);
    } catch {
      setPreviewRegions((regions) => ({ ...regions, [change.field.field_key]: change.after }));
    } finally {
      setHistoryWorking(false);
    }
  }

  async function redo() {
    const change = future.at(-1);
    if (!change || historyWorking) return;
    setHistoryWorking(true);
    setPreviewRegions((regions) => ({ ...regions, [change.field.field_key]: change.after }));
    try {
      await onPersist(currentField(change.field), change.after);
      setFuture((items) => items.slice(0, -1));
      setPast((items) => [...items, change]);
    } catch {
      setPreviewRegions((regions) => ({ ...regions, [change.field.field_key]: change.before }));
    } finally {
      setHistoryWorking(false);
    }
  }

  function currentField(fallback: TemplateField): TemplateField {
    return version.fields.find((field) => field.field_key === fallback.field_key) ?? fallback;
  }

  function alignSelected(alignment: Alignment) {
    const field = version.fields.find((item) => item.field_key === selectedFieldKey);
    if (!field || !editable) return;
    const current = previewRegions[field.field_key] ?? field.region;
    const next = alignRect(current, alignment, PROTECTED_ZONES);
    if (next === current || sameRect(next, current)) {
      onReject(PROTECTED_PLACEMENT_MESSAGE);
      return;
    }
    setPreviewRegions((regions) => ({ ...regions, [field.field_key]: next }));
    void persistOrRestore(field, next, current, true);
  }

  return (
    <section className="studio-canvas" aria-label="模板字段画布">
      <div className="canvas-toolbar">
        <div><span className="eyebrow">标准画布</span><strong>{version.page.size} · V{version.version}</strong></div>
        <div className="canvas-tool-actions" aria-label="画布工具">
          <button type="button" disabled={!editable || historyWorking || past.length === 0} onClick={() => void undo()}>撤销</button>
          <button type="button" disabled={!editable || historyWorking || future.length === 0} onClick={() => void redo()}>重做</button>
          <button type="button" className={gridSnap ? "active" : ""} aria-pressed={gridSnap} onClick={() => setGridSnap((value) => !value)}>网格吸附</button>
          <button type="button" aria-label="缩小画布" disabled={zoom <= 0.6} onClick={() => setZoom((value) => Math.max(0.6, value - 0.1))}>−</button>
          <output aria-label="画布缩放">{Math.round(zoom * 100)}%</output>
          <button type="button" aria-label="放大画布" disabled={zoom >= 1.6} onClick={() => setZoom((value) => Math.min(1.6, value + 0.1))}>＋</button>
        </div>
      </div>
      <div className="alignment-toolbar" aria-label="字段对齐">
        {(["left", "horizontal-center", "right", "top", "vertical-center", "bottom"] as Alignment[]).map((alignment) => (
          <button key={alignment} type="button" disabled={!editable || selectedFieldKey === null || historyWorking} onClick={() => alignSelected(alignment)}>{alignmentLabel(alignment)}</button>
        ))}
      </div>
      <div className="canvas-viewport">
        <div className="millimeter-ruler horizontal-ruler" aria-label="横向毫米标尺">{rulerTicks(version.page.width_mm, "horizontal")}</div>
        <div className="millimeter-ruler vertical-ruler" aria-label="纵向毫米标尺">{rulerTicks(version.page.height_mm, "vertical")}</div>
        <div
          ref={paperRef}
          data-testid="template-canvas-paper"
          className={`paper-preview template-canvas-paper ${editable ? "editable" : "read-only"}`}
          style={{ aspectRatio: `${version.page.width_mm} / ${version.page.height_mm}`, transform: `scale(${zoom})` }}
        >
        <div className="printable-boundary" aria-hidden="true" />
        <span className="marker top-left">10</span>
        <span className="marker top-right">11</span>
        <span className="marker bottom-left">13</span>
        <span className="marker bottom-right">12</span>
        <ProtectedZone label="模板 QR" region={QR_SAFE_ZONE} className="qr-zone" />
        <ProtectedZone label="纸张实例码" region={SHEET_CODE_SAFE_ZONE} className="sheet-zone" />
        {version.static_elements.filter((element) => element.kind === "TABLE_GRID").map((grid) => (
          <div key={grid.element_id} className="template-grid-overlay" style={rectStyle(grid.region)} aria-label={`${grid.text || "明细表"}，${grid.rows} 行 ${grid.columns} 列`}>
            {Array.from({ length: Math.max(0, grid.rows - 1) }, (_, index) => <i key={`row-${index}`} className="grid-row-line" style={{ top: `${((index + 1) / grid.rows) * 100}%` }} />)}
            {gridColumnOffsets(grid).map((offset, index) => <i key={`column-${index}`} className="grid-column-line" style={{ left: `${offset * 100}%` }} />)}
            <span>{grid.text || "明细表"}</span>
          </div>
        ))}
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
              <small>{field.field_key} · {formatMillimeters(region, version)}</small>
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
      </div>
    </section>
  );
}

function gridColumnOffsets(grid: TemplateVersion["static_elements"][number]): number[] {
  const weights = grid.column_weights.length === grid.columns
    ? grid.column_weights
    : Array(grid.columns).fill(1) as number[];
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  let consumed = 0;
  return weights.slice(0, -1).map((weight) => {
    consumed += weight;
    return consumed / total;
  });
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

function rulerTicks(extentMm: number, orientation: "horizontal" | "vertical") {
  const ticks: React.ReactNode[] = [];
  for (let value = 0; value <= extentMm; value += 10) {
    const position = `${value / extentMm * 100}%`;
    ticks.push(<span key={value} style={orientation === "horizontal" ? { left: position } : { top: position }}>{value}</span>);
  }
  return ticks;
}

function alignmentLabel(alignment: Alignment): string {
  return {
    left: "左对齐",
    "horizontal-center": "水平居中",
    right: "右对齐",
    top: "顶对齐",
    "vertical-center": "垂直居中",
    bottom: "底对齐",
  }[alignment];
}

function formatMillimeters(region: TemplateRect, version: TemplateVersion): string {
  const millimeters = rectInMillimeters(region, version.page);
  return `${millimeters.x}×${millimeters.y} / ${millimeters.width}×${millimeters.height} mm`;
}
