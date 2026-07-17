import { type TemplateApi, type TemplateField, type TemplateVersion } from "@form-detection/api-client";
import { useEffect, useMemo, useState } from "react";

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
  const [reload, setReload] = useState(0);
  const [scale, setScale] = useState(1);
  const [fieldQuery, setFieldQuery] = useState("");
  const [selectedFieldKey, setSelectedFieldKey] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setVersion(null);
    void api.getVersion(versionId)
      .then((loaded) => {
        if (!active) return;
        setVersion(loaded);
        setSelectedFieldKey(loaded.fields[0]?.field_key ?? null);
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "无法读取模板版本。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [api, reload, versionId]);

  const visibleFields = useMemo(() => {
    const normalized = fieldQuery.trim().toLowerCase();
    return version?.fields.filter((field) => !normalized
      || field.display_name.toLowerCase().includes(normalized)
      || field.field_key.toLowerCase().includes(normalized)) ?? [];
  }, [fieldQuery, version]);

  async function tune() {
    setTuning(true);
    setError(null);
    try {
      await onTune(versionId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "无法创建调优草稿。");
      setTuning(false);
    }
  }

  return (
    <main className="template-center template-preview-page">
      <header className="template-center-header">
        <div><button className="text-button" onClick={onBack}>返回模板库</button><span className="eyebrow">模板版本 · 只读预览</span><h1>{version?.display_name ?? "模板预览"}</h1><p>{version ? `${version.description || "尚未填写用途说明"}` : "已发布内容不可直接修改。"}</p></div>
        {version ? <span className={`status-pill ${version.status === "PUBLISHED" ? "success" : "warning"}`}>{version.status === "PUBLISHED" ? "已发布" : "已退役"} V{version.version}</span> : null}
      </header>
      {error ? <div className="error-banner" role="alert"><span>{error}</span><button className="text-button" onClick={() => setReload((value) => value + 1)}>重试</button></div> : null}
      {loading ? <section className="preview-loading">正在载入只读版本…</section> : null}
      {version ? (
        <section className="template-preview-layout">
          <section className="preview-paper-stage" aria-label="纸张预览">
            <div className="evidence-toolbar" role="toolbar" aria-label="模板预览工具">
              <button type="button" onClick={() => setScale((value) => Math.min(2, Number((value + 0.1).toFixed(1))))}>放大</button>
              <button type="button" onClick={() => setScale((value) => Math.max(0.5, Number((value - 0.1).toFixed(1))))}>缩小</button>
              <button type="button" onClick={() => setScale(0.8)}>适合页面</button>
              <button type="button" onClick={() => setScale(1.2)}>适合宽度</button>
              <button type="button" onClick={() => setScale(1)}>复位</button>
              <span>{Math.round(scale * 100)}%</span>
            </div>
            <div
              className="paper-preview preview-paper"
              data-testid="template-preview-paper"
              style={{ aspectRatio: paperRatio(version), transform: `scale(${scale})`, transformOrigin: "top center" }}
            >
              <strong>{version.display_name} · V{version.version}</strong>
              <span className="marker top-left">10</span><span className="marker top-right">11</span><span className="marker bottom-left">13</span><span className="marker bottom-right">12</span>
              <div className="safe-zone">模板 QR 安全区</div>
              {version.fields.map((field) => (
                <button
                  type="button"
                  className={`preview-field ${field.field_key === selectedFieldKey ? "selected" : ""}`}
                  key={field.field_key}
                  style={fieldStyle(field)}
                  aria-label={`预览字段 ${field.display_name}`}
                  aria-pressed={field.field_key === selectedFieldKey}
                  onClick={() => setSelectedFieldKey(field.field_key)}
                ><span>{field.display_name}</span></button>
              ))}
            </div>
          </section>
          <aside className="preview-inspector">
            <div><span className="eyebrow">页面与字段</span><h2>{version.page.size} · {version.page.orientation === "portrait" ? "纵向" : version.page.orientation}</h2><p className="muted">{version.fields.length} 个字段</p></div>
            <section>
              <h3>字段列表</h3>
              <label>搜索字段<input value={fieldQuery} onChange={(event) => setFieldQuery(event.target.value)} /></label>
              <ul className="preview-field-list">
                {visibleFields.length ? visibleFields.map((field) => (
                  <li key={field.field_key} className={field.field_key === selectedFieldKey ? "selected" : ""}>
                    <button type="button" aria-label={`选择字段 ${field.display_name}`} onClick={() => setSelectedFieldKey(field.field_key)}>{field.display_name}</button>
                  </li>
                )) : <li className="muted">没有匹配字段。</li>}
              </ul>
            </section>
            <section>
              <h3>打印产物</h3>
              <div className="preview-artifacts">
                {version.artifacts.length ? version.artifacts.map((artifact) => (
                  <a key={artifact.artifact_id} className="candidate-chip" href={artifact.download_url} target="_blank" rel="noreferrer">下载 {artifact.kind.toUpperCase()}</a>
                )) : <p className="muted">尚无可下载的打印产物。</p>}
              </div>
            </section>
            <details>
              <summary>高级信息</summary>
              <p>模板编号：{version.template_key}</p>
              <p>标准画布：{version.page.canonical_dpi} DPI · {version.page.canonical_width_px} × {version.page.canonical_height_px}</p>
              <ul>{version.fields.map((field) => <li key={field.field_key}>{field.field_key} · {field.recognition_engine}</li>)}</ul>
              <ul>{version.artifacts.map((artifact) => <li key={artifact.artifact_id}>{artifact.download_name} · SHA-256 {artifact.sha256}</li>)}</ul>
            </details>
            {version.status === "PUBLISHED" ? <button className="button button-primary" disabled={tuning} onClick={() => void tune()}>{tuning ? "正在创建草稿…" : "基于此模板调优"}</button> : <p className="inline-warning">已退役模板仅供历史追溯，不能再创建调优版本。</p>}
          </aside>
        </section>
      ) : null}
    </main>
  );
}

function paperRatio(version: TemplateVersion): string { return `${version.page.width_mm} / ${version.page.height_mm}`; }
function fieldStyle(field: TemplateField): React.CSSProperties {
  return {
    left: `${field.region.x * 100}%`,
    top: `${field.region.y * 100}%`,
    width: `${field.region.width * 100}%`,
    height: `${field.region.height * 100}%`,
  };
}
