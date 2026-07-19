import type { TemplateStaticElement } from "@form-detection/api-client";
import { useEffect, useState } from "react";

type Props = {
  grid: TemplateStaticElement | null;
  editable: boolean;
  onSave: (grid: TemplateStaticElement) => Promise<void>;
};

export function GridInspector({ grid, editable, onSave }: Props) {
  const [rows, setRows] = useState(1);
  const [columns, setColumns] = useState(1);
  const [weights, setWeights] = useState("1");
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    if (!grid) return;
    setRows(grid.rows);
    setColumns(grid.columns);
    setWeights((grid.column_weights.length ? grid.column_weights : Array(grid.columns).fill(1)).join(" : "));
    setError(null);
  }, [grid]);

  if (!grid) {
    return (
      <aside className="studio-card grid-inspector empty-inspector">
        <h2>明细表设置</h2>
        <p className="muted">从左侧选择一个明细表后，可调整固定行列和比例列宽。</p>
      </aside>
    );
  }

  async function save() {
    if (!grid) return;
    const currentGrid = grid;
    const parsedWeights = weights
      .split(/[:：,，\s]+/u)
      .filter(Boolean)
      .map(Number);
    if (rows < 1 || rows > 30 || columns < 1 || columns > 12) {
      setError("行数须为 1–30，列数须为 1–12。");
      return;
    }
    if (parsedWeights.length !== columns || parsedWeights.some((value) => !Number.isFinite(value) || value <= 0)) {
      setError(`请输入 ${columns} 个大于 0 的列宽比例，例如 2 : 1 : 1。`);
      return;
    }
    setWorking(true);
    setError(null);
    try {
      await onSave({ ...currentGrid, rows, columns, column_weights: parsedWeights });
    } catch {
      // The parent owns the business error banner; keep the edited values for retry.
    } finally {
      setWorking(false);
    }
  }

  return (
    <aside className="studio-card grid-inspector">
      <div className="inspector-heading">
        <div><span className="eyebrow">受控表格</span><h2>{grid.text || "明细表"}</h2></div>
        <span className="status-pill neutral">固定网格</span>
      </div>
      <p className="muted">只调整表格结构，不允许插入脚本或自由网页内容。</p>
      <div className="grid-settings-form">
        <label>行数<input aria-label="表格行数" type="number" min="1" max="30" value={rows} disabled={!editable || working} onChange={(event) => setRows(Number(event.target.value))} /></label>
        <label>列数<input aria-label="表格列数" type="number" min="1" max="12" value={columns} disabled={!editable || working} onChange={(event) => setColumns(Number(event.target.value))} /></label>
        <label className="grid-weight-setting">比例列宽<input aria-label="表格比例列宽" value={weights} disabled={!editable || working} onChange={(event) => setWeights(event.target.value)} /><span className="muted">按从左到右输入，用冒号分隔。</span></label>
      </div>
      {error && <p className="inline-warning" role="alert">{error}</p>}
      <button className="button button-secondary" disabled={!editable || working} onClick={() => void save()}>{working ? "正在保存…" : "保存表格设置"}</button>
    </aside>
  );
}
