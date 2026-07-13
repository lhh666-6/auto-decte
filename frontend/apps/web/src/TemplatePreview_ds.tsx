import { type TemplateApi, type TemplateVersion } from "@form-detection/api-client";
import { useEffect, useState } from "react";

type Props = {
  api: TemplateApi;
  versionId: string;
  onBack: () => void;
  onTune: (versionId: string) => Promise<void>;
};

export function TemplatePreview({ api, versionId, onBack, onTune }: Props) {
  const [version, setVersion] = useState<TemplateVersion | null>(null);
  const [loading, setLoading] = useState(true);
  const [tuning, setTuning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void api.getVersion(versionId)
      .then((item) => active && setVersion(item))
      .catch((cause: unknown) => active && setError(cause instanceof Error ? cause.message : "无法读取模板版本。"))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [api, versionId]);

  async function tune() {
    setTuning(true);
    setError(null);
    try {
      await onTune(versionId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "无法创建调优草稿。" );
      setTuning(false);
    }
  }

  return <main className="template-center template-preview-page">
    <header className="template-center-header"><div><button className="text-button" onClick={onBack}>返回模板库</button><span className="eyebrow">已发布版本 · 只读预览</span><h1>{version?.template_key ?? "模板预览"}</h1><p>已发布内容不可直接修改。调优会创建保留父版本关系的新草稿。</p></div>{version && <span className="status-pill success">已发布 V{version.version}</span>}</header>
    {error && <div className="error-banner">{error}</div>}
    {loading && <section className="preview-loading">正在载入只读版本…</section>}
    {version && <section className="template-preview-layout">
      <section className="preview-paper-stage" aria-label="纸张预览">
        <div className="paper-preview preview-paper" style={{ aspectRatio: paperRatio(version) }}>
          <strong>{version.template_key} · V{version.version}</strong>
          <span className="marker top-left">10</span><span className="marker top-right">11</span><span className="marker bottom-left">13</span><span className="marker bottom-right">12</span>
          <div className="safe-zone">模板 QR 安全区</div>
          {version.fields.map((field) => <div className="preview-field" key={field.field_key} style={{ left: `${field.region.x * 100}%`, top: `${field.region.y * 100}%`, width: `${field.region.width * 100}%`, height: `${field.region.height * 100}%` }}><span>{field.display_name}</span></div>)}
        </div>
      </section>
      <aside className="preview-inspector">
        <div><span className="eyebrow">页面与字段</span><h2>{version.page.size} · {version.page.orientation === "portrait" ? "纵向" : version.page.orientation}</h2><p className="muted">{version.fields.length} 个字段 · 标准 {version.page.canonical_dpi} DPI 画布</p></div>
        <section><h3>字段摘要</h3><ul className="preview-field-list">{version.fields.length ? version.fields.map((field) => <li key={field.field_key}><strong>{field.display_name}</strong><span>{field.field_key} · {field.recognition_engine}</span></li>) : <li className="muted">此模板尚未配置字段。</li>}</ul></section>
        <section><h3>打印产物</h3><div className="preview-artifacts">{version.artifacts.length ? version.artifacts.map((artifact) => <a key={artifact.artifact_id} className="candidate-chip" href={artifact.download_url} target="_blank" rel="noreferrer">打开 {artifact.download_name}</a>) : <p className="muted">尚无可下载的打印产物。</p>}</div></section>
        <button className="button button-primary" disabled={tuning} onClick={() => void tune()}>{tuning ? "正在创建草稿…" : "基于此模板调优"}</button>
      </aside>
    </section>}
  </main>;
}

function paperRatio(version: TemplateVersion): string { return `${version.page.width_mm} / ${version.page.height_mm}`; }
