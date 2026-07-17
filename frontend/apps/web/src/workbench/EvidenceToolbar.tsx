interface EvidenceToolbarProps {
  mode: "original" | "corrected";
  hasOriginal: boolean;
  hasCorrected: boolean;
  zoomPercent: number;
  showFieldBoxes: boolean;
  onModeChange: (mode: "original" | "corrected") => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onRotate: () => void;
  onReset: () => void;
  onToggleFieldBoxes: () => void;
}

export function EvidenceToolbar({
  mode,
  hasOriginal,
  hasCorrected,
  zoomPercent,
  showFieldBoxes,
  onModeChange,
  onZoomIn,
  onZoomOut,
  onRotate,
  onReset,
  onToggleFieldBoxes,
}: EvidenceToolbarProps) {
  return (
    <div className="evidence-toolbar" role="toolbar" aria-label="图片工具">
      <div className="evidence-variant-switch" aria-label="图片版本">
        <button
          type="button"
          disabled={!hasOriginal}
          aria-pressed={mode === "original"}
          onClick={() => onModeChange("original")}
        >原图</button>
        <button
          type="button"
          disabled={!hasCorrected}
          aria-pressed={mode === "corrected"}
          onClick={() => onModeChange("corrected")}
        >校正图</button>
      </div>
      <button type="button" aria-label="缩小" onClick={onZoomOut}>−</button>
      <span aria-label="当前缩放比例">{zoomPercent}%</span>
      <button type="button" aria-label="放大" onClick={onZoomIn}>+</button>
      <button type="button" aria-label="顺时针旋转" onClick={onRotate}>旋转</button>
      <button type="button" aria-label="复位视图" onClick={onReset}>复位</button>
      <button type="button" onClick={onToggleFieldBoxes}>
        {showFieldBoxes ? "隐藏字段框" : "显示字段框"}
      </button>
    </div>
  );
}
