import { ApiRequestError, TemplateApi, type PreflightReport, type TemplateVersion } from "@form-detection/api-client";
import { useMemo, useState } from "react";

type Props = { onBack: () => void };

export function TemplateStudio({ onBack }: Props) {
  const api = useMemo(() => new TemplateApi("/api/v1"), []);
  const [key, setKey] = useState("PAYROLL_HOURLY");
  const [page, setPage] = useState<"A4" | "A5">("A4");
  const [version, setVersion] = useState<TemplateVersion | null>(null);
  const [report, setReport] = useState<PreflightReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [field, setField] = useState({ field_key: "worker_name", display_name: "姓名", data_type: "text", input_type: "text_box", recognition_engine: "manual", minimum_prefill_confidence: 0.97, x: 0.1, y: 0.2, width: 0.22, height: 0.05 });

  async function createDraft() { try { setError(null); setReport(null); setVersion(await api.createDraft(key.trim(), page)); } catch (cause) { setError(message(cause)); } }
  async function addField() { if (!version) return; try { setError(null); setVersion(await api.addField(version.version_id, { ...field, region: { x: field.x, y: field.y, width: field.width, height: field.height } })); } catch (cause) { setError(message(cause)); } }
  async function preflight() { if (!version) return; try { setError(null); const next = await api.preflight(version.version_id); setReport(next); setVersion((current) => current ? { ...current, status: next.status } : current); } catch (cause) { setError(message(cause)); } }
  async function publish() { if (!version) return; try { setError(null); setVersion(await api.publish(version.version_id)); } catch (cause) { setError(message(cause)); } }

  return <main className="template-studio">
    <header className="studio-header"><button className="text-button" onClick={onBack}>← 返回审核工作台</button><div><span className="eyebrow">模板中心</span><h1>纸质表单设计器</h1><p>发布后自动生成模板二维码、纸张实例码和可打印文件。</p></div><span className={`status-pill ${version?.status === "PUBLISHED" ? "success" : "warning"}`}>{version?.status ?? "未创建草稿"}</span></header>
    {error && <div className="error-banner">{error}</div>}
    <section className="studio-grid"><aside className="studio-card"><h2>模板版本</h2><label>模板键<input value={key} onChange={(event) => setKey(event.target.value.toUpperCase())} /></label><label>页面<select value={page} onChange={(event) => setPage(event.target.value as "A4" | "A5")}><option>A4</option><option>A5</option></select></label><button className="button button-primary" onClick={() => void createDraft()}>创建草稿</button><p className="muted">推荐：计时、标准计件、固定生产网格、设备工序。</p></aside>
    <section className="studio-canvas"><div className="paper-preview"><b>{version?.template_key ?? key} · {page}</b><span className="marker top-left">10</span><span className="marker top-right">11</span><span className="marker bottom-left">13</span><span className="marker bottom-right">12</span><div className="safe-zone">模板 QR 安全区</div>{version?.fields.map((item) => <div key={item.field_key} className="template-field">{item.field_key} · {item.recognition_engine} · ≥{item.minimum_prefill_confidence}</div>)}</div></section>
    <aside className="studio-card"><h2>字段配置</h2><label>字段键<input value={field.field_key} onChange={(event) => setField({ ...field, field_key: event.target.value })} /></label><label>显示名<input value={field.display_name} onChange={(event) => setField({ ...field, display_name: event.target.value })} /></label><label>识别引擎<select value={field.recognition_engine} onChange={(event) => setField({ ...field, recognition_engine: event.target.value })}><option value="manual">人工填写</option><option value="digit_template">数字格识别</option><option value="omr">OMR 勾选</option></select></label><label>自动预填阈值<input type="number" step="0.01" min="0" max="1" value={field.minimum_prefill_confidence} onChange={(event) => setField({ ...field, minimum_prefill_confidence: Number(event.target.value) })} /></label><div className="coordinate-grid">{(["x", "y", "width", "height"] as const).map((name) => <label key={name}>{name}<input type="number" step="0.01" min="0" max="1" value={field[name]} onChange={(event) => setField({ ...field, [name]: Number(event.target.value) })} /></label>)}</div><button className="button button-secondary" disabled={!version || version.status === "PUBLISHED"} onClick={() => void addField()}>加入字段</button><button className="button button-secondary" disabled={!version || version.status === "PUBLISHED"} onClick={() => void preflight()}>运行发布预检</button><button className="button button-primary" disabled={!version || version.status !== "READY_TO_PUBLISH"} onClick={() => void publish()}>发布模板</button></aside></section>
    <section className="studio-card preflight"><h2>发布预检与打印件</h2>{report ? (report.ok ? <p className="inline-success">预检通过：可以发布。</p> : report.issues.map((issue) => <p className="inline-warning" key={issue.code}>{issue.code}：{issue.detail}</p>)) : <p className="muted">创建草稿后运行预检。</p>}{version?.artifacts.map((artifact) => <a key={artifact.artifact_id} className="candidate-chip" href={artifact.download_url} target="_blank" rel="noreferrer">打开 {artifact.download_name}</a>)}</section>
  </main>;
}

function message(cause: unknown): string { return cause instanceof ApiRequestError ? `${cause.code}：${cause.message}` : "模板请求无法完成。"; }
