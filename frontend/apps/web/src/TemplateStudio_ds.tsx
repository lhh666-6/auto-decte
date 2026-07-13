import { ApiRequestError, TemplateApi, type PreflightReport, type TemplateVersion } from "@form-detection/api-client";
import { useEffect, useMemo, useState } from "react";

import { TemplateLibrary } from "./TemplateLibrary_ds";
import { TemplatePreview } from "./TemplatePreview_ds";
import { nextScreen, type StudioAction, type StudioScreen } from "./template-studio-state";

type Props = { onBack: () => void };

export function TemplateStudio({ onBack }: Props) {
  const api = useMemo(() => new TemplateApi("/api/v1"), []);
  const [screen, setScreen] = useState<StudioScreen>({ kind: "library" });

  function navigate(action: StudioAction) { setScreen((current) => nextScreen(current, action)); }
  async function createBlank(templateKey: string, pageSize: "A4" | "A5") {
    const draft = await api.createDraft(templateKey, pageSize);
    navigate({ type: "draftCreated", versionId: draft.version_id });
  }
  async function cloneAndOpenEditor(versionId: string) {
    const draft = await api.clone(versionId);
    navigate({ type: "cloneSucceeded", sourceVersionId: versionId, versionId: draft.version_id });
  }

  if (screen.kind === "library") return <TemplateLibrary api={api} onBack={onBack} onSelectPublished={(versionId) => navigate({ type: "select", versionId })} onOpenDraft={(versionId) => navigate({ type: "editDraft", versionId })} onCreateBlank={createBlank} />;
  if (screen.kind === "preview") return <TemplatePreview api={api} versionId={screen.versionId} onBack={() => navigate({ type: "backToLibrary" })} onTune={cloneAndOpenEditor} />;
  return <TemplateEditor api={api} versionId={screen.versionId} onBack={() => navigate({ type: "backToLibrary" })} />;
}

function TemplateEditor({ api, versionId, onBack }: { api: TemplateApi; versionId: string; onBack: () => void }) {
  const [version, setVersion] = useState<TemplateVersion | null>(null);
  const [report, setReport] = useState<PreflightReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [field, setField] = useState({ field_key: "worker_name", display_name: "姓名", data_type: "text", input_type: "text_box", recognition_engine: "manual", minimum_prefill_confidence: 0.97, x: 0.1, y: 0.2, width: 0.22, height: 0.05 });

  useEffect(() => {
    let active = true;
    setError(null);
    setReport(null);
    void api.getVersion(versionId).then((item) => active && setVersion(item)).catch((cause: unknown) => active && setError(message(cause)));
    return () => { active = false; };
  }, [api, versionId]);

  async function addField() { if (!version) return; try { setError(null); setVersion(await api.addField(version.version_id, { ...field, region: { x: field.x, y: field.y, width: field.width, height: field.height } })); } catch (cause) { setError(message(cause)); } }
  async function preflight() { if (!version) return; try { setError(null); const next = await api.preflight(version.version_id); setReport(next); setVersion((current) => current ? { ...current, status: next.status } : current); } catch (cause) { setError(message(cause)); } }
  async function publish() { if (!version) return; try { setError(null); setVersion(await api.publish(version.version_id)); } catch (cause) { setError(message(cause)); } }

  return <main className="template-studio">
    <header className="studio-header"><button className="text-button" onClick={onBack}>返回模板库</button><div><span className="eyebrow">草稿设计器</span><h1>{version?.template_key ?? "正在加载草稿…"}</h1><p>此草稿可继续配置字段、运行预检并发布。</p></div><span className={`status-pill ${version?.status === "PUBLISHED" ? "success" : "warning"}`}>{version?.status ?? "加载中"}</span></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <section className="studio-grid"><aside className="studio-card"><h2>模板版本</h2><p className="muted">{version ? `V${version.version} · ${version.page.size}` : "读取版本信息…"}</p><p className="muted">已发布版本只读；新版本请从预览页调优创建。</p></aside>
    <section className="studio-canvas"><div className="paper-preview"><b>{version?.template_key ?? "草稿"} · {version?.page.size ?? "A4"}</b><span className="marker top-left">10</span><span className="marker top-right">11</span><span className="marker bottom-left">13</span><span className="marker bottom-right">12</span><div className="safe-zone">模板 QR 安全区</div>{version?.fields.map((item) => <div key={item.field_key} className="template-field">{item.field_key} · {item.recognition_engine} · ≥{item.minimum_prefill_confidence}</div>)}</div></section>
    <aside className="studio-card"><h2>字段配置</h2><label>字段键<input value={field.field_key} onChange={(event) => setField({ ...field, field_key: event.target.value })} /></label><label>显示名<input value={field.display_name} onChange={(event) => setField({ ...field, display_name: event.target.value })} /></label><label>识别引擎<select value={field.recognition_engine} onChange={(event) => setField({ ...field, recognition_engine: event.target.value })}><option value="manual">人工填写</option><option value="digit_template">数字格识别</option><option value="omr">OMR 勾选</option></select></label><label>自动预填阈值<input type="number" step="0.01" min="0" max="1" value={field.minimum_prefill_confidence} onChange={(event) => setField({ ...field, minimum_prefill_confidence: Number(event.target.value) })} /></label><div className="coordinate-grid">{(["x", "y", "width", "height"] as const).map((name) => <label key={name}>{name}<input type="number" step="0.01" min="0" max="1" value={field[name]} onChange={(event) => setField({ ...field, [name]: Number(event.target.value) })} /></label>)}</div><button className="button button-secondary" disabled={!version || version.status === "PUBLISHED"} onClick={() => void addField()}>加入字段</button><button className="button button-secondary" disabled={!version || version.status === "PUBLISHED"} onClick={() => void preflight()}>运行发布预检</button><button className="button button-primary" disabled={!version || version.status !== "READY_TO_PUBLISH"} onClick={() => void publish()}>发布模板</button></aside></section>
    <section className="studio-card preflight"><h2>发布预检与打印件</h2>{report ? (report.ok ? <p className="inline-success">预检通过：可以发布。</p> : report.issues.map((issue) => <p className="inline-warning" key={issue.code}>{issue.code}：{issue.detail}</p>)) : <p className="muted">加载草稿后可运行预检。</p>}{version?.artifacts.map((artifact) => <a key={artifact.artifact_id} className="candidate-chip" href={artifact.download_url} target="_blank" rel="noreferrer">打开 {artifact.download_name}</a>)}</section>
  </main>;
}

function message(cause: unknown): string { return cause instanceof ApiRequestError ? `${cause.code}：${cause.message}` : "模板请求无法完成。"; }
