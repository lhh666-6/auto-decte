import type { EvidenceItem, ReviewField } from "@form-detection/api-client";
import { useEffect, useMemo, useRef, useState } from "react";

import { selectReviewEvidence } from "../review-model";
import {
  DEFAULT_EVIDENCE_TRANSFORM,
  resetEvidenceTransform,
  rotateEvidenceClockwise,
  translateEvidence,
  zoomEvidence,
  type EvidenceTransform,
} from "./evidence-transform";
import { EvidenceToolbar } from "./EvidenceToolbar";

interface EvidenceViewerProps {
  evidence: readonly EvidenceItem[];
  fields: readonly ReviewField[];
  selectedFieldId: string | null;
  hoveredFieldId?: string | null;
  onSelectField: (fieldId: string) => void;
  onHoverField?: (fieldId: string | null) => void;
}

export function EvidenceViewer({
  evidence,
  fields,
  selectedFieldId,
  hoveredFieldId: controlledHoveredFieldId,
  onSelectField,
  onHoverField,
}: EvidenceViewerProps) {
  const original = evidence.find((item) => item.type === "ORIGINAL_IMAGE") ?? null;
  const corrected = evidence.find((item) => item.type === "CORRECTED_IMAGE") ?? null;
  const preferred = selectReviewEvidence(evidence);
  const [mode, setMode] = useState<"original" | "corrected">(
    preferred.coordinateSpace === "canonical" ? "corrected" : "original",
  );
  const [transform, setTransform] = useState<EvidenceTransform>(DEFAULT_EVIDENCE_TRANSFORM);
  const [showFieldBoxes, setShowFieldBoxes] = useState(true);
  const [imageSize, setImageSize] = useState({ width: 1, height: 1 });
  const [internalHoveredFieldId, setInternalHoveredFieldId] = useState<string | null>(null);
  const dragPoint = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (mode === "original" && !original && corrected) setMode("corrected");
    if (mode === "corrected" && !corrected && original) setMode("original");
  }, [corrected, mode, original]);

  const activeEvidence = mode === "corrected" ? corrected ?? original : original ?? corrected;
  const canonicalCoordinates = mode === "corrected" && activeEvidence?.type === "CORRECTED_IMAGE";
  const hoveredFieldId = controlledHoveredFieldId === undefined
    ? internalHoveredFieldId
    : controlledHoveredFieldId;
  const selectedCrop = useMemo(() => evidence.find((item) => (
    item.type === "FIELD_CROP" && item.related_field_id === selectedFieldId
  )) ?? null, [evidence, selectedFieldId]);

  function changeHover(fieldId: string | null) {
    if (controlledHoveredFieldId === undefined) setInternalHoveredFieldId(fieldId);
    onHoverField?.(fieldId);
  }

  return (
    <section className="evidence-panel evidence-viewer" aria-label="表单图像证据">
      <EvidenceToolbar
        mode={mode}
        hasOriginal={original !== null}
        hasCorrected={corrected !== null}
        zoomPercent={transform.zoomPercent}
        showFieldBoxes={showFieldBoxes}
        onModeChange={setMode}
        onZoomIn={() => setTransform((current) => zoomEvidence(current, 25))}
        onZoomOut={() => setTransform((current) => zoomEvidence(current, -25))}
        onRotate={() => setTransform(rotateEvidenceClockwise)}
        onReset={() => setTransform(resetEvidenceTransform)}
        onToggleFieldBoxes={() => setShowFieldBoxes((current) => !current)}
      />
      {!canonicalCoordinates && activeEvidence && (
        <div className="alignment-warning" role="status">原图没有模板坐标字段框</div>
      )}
      <div
        className="canvas-stage evidence-canvas-stage"
        aria-label="图片查看区域"
        onWheel={(event) => {
          event.preventDefault();
          setTransform((current) => zoomEvidence(current, event.deltaY < 0 ? 25 : -25));
        }}
        onPointerMove={(event) => {
          const previous = dragPoint.current;
          if (!previous) return;
          setTransform((current) => translateEvidence(
            current,
            event.clientX - previous.x,
            event.clientY - previous.y,
          ));
          dragPoint.current = { x: event.clientX, y: event.clientY };
        }}
        onPointerUp={() => { dragPoint.current = null; }}
        onPointerCancel={() => { dragPoint.current = null; }}
      >
        {activeEvidence ? (
          <div
            className="image-wrap evidence-transform-layer"
            data-testid="evidence-transform"
            style={{
              transform: `translate(${transform.offsetX}px, ${transform.offsetY}px) rotate(${transform.rotationDegrees}deg) scale(${transform.zoomPercent / 100})`,
            }}
            onPointerDown={(event) => {
              if ((event.target as HTMLElement).closest(".field-overlay")) return;
              dragPoint.current = { x: event.clientX, y: event.clientY };
            }}
          >
            <img
              src={activeEvidence.download_url}
              alt={canonicalCoordinates ? "校正后的表单" : "原始表单"}
              draggable={false}
              onLoad={(event) => setImageSize({
                width: Math.max(1, event.currentTarget.naturalWidth),
                height: Math.max(1, event.currentTarget.naturalHeight),
              })}
            />
            {canonicalCoordinates && showFieldBoxes && fields.map((field) => {
              const selected = field.field_id === selectedFieldId;
              const hovered = field.field_id === hoveredFieldId;
              return (
                <button
                  key={field.field_id}
                  type="button"
                  className={[
                    "field-overlay",
                    selected ? "selected" : "",
                    selectedFieldId !== null && !selected ? "dimmed" : "",
                    hovered ? "hovered" : "",
                  ].filter(Boolean).join(" ")}
                  style={fieldBoxStyle(field.source_region, imageSize)}
                  aria-label={`定位字段 ${field.field_id}`}
                  onMouseEnter={() => changeHover(field.field_id)}
                  onMouseLeave={() => changeHover(null)}
                  onFocus={() => changeHover(field.field_id)}
                  onBlur={() => changeHover(null)}
                  onClick={() => onSelectField(field.field_id)}
                >
                  <span>{field.display_name ?? field.field_name}</span>
                </button>
              );
            })}
          </div>
        ) : <div className="empty-canvas">当前表单没有可用图片证据</div>}
      </div>
      <section className="selected-field-crop" aria-label="选中字段裁片">
        <strong>字段裁片</strong>
        {selectedCrop ? (
          <img src={selectedCrop.download_url} alt="当前字段裁片" />
        ) : <span className="muted">该字段没有可用裁片</span>}
      </section>
    </section>
  );
}

function fieldBoxStyle(
  region: Readonly<Record<string, number>>,
  imageSize: { width: number; height: number },
) {
  const width = region.width ?? region.w ?? 0;
  const height = region.height ?? region.h ?? 0;
  return {
    left: `${((region.x ?? 0) / imageSize.width) * 100}%`,
    top: `${((region.y ?? 0) / imageSize.height) * 100}%`,
    width: `${(width / imageSize.width) * 100}%`,
    height: `${(height / imageSize.height) * 100}%`,
  };
}
