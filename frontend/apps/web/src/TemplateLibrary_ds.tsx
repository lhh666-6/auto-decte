import { isEditableTemplateStatus, type TemplateApi, type TemplateLibraryItem, type TemplatePage } from "@form-detection/api-client";
import { useCallback, useEffect, useMemo, useState } from "react";

type Props = {
  api: TemplateApi;
  onBack: () => void;
  onSelectPublished: (versionId: string) => void;
  onOpenDraft: (versionId: string) => void;
  onCreateBlank: (
    templateKey: string,
    pageSize: "A4" | "A5",
    displayName: string,
    description: string,
  ) => Promise<void>;
};

type StatusFilter = "ALL" | "PUBLISHED" | "EDITABLE";

export function TemplateLibrary({ api, onBack, onSelectPublished, onOpenDraft, onCreateBlank }: Props) {
  const [templates, setTemplates] = useState<TemplateLibraryItem[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<StatusFilter>("ALL");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templateKey, setTemplateKey] = useState("NEW_TEMPLATE");
  const [displayName, setDisplayName] = useState("新建模板");
  const [description, setDescription] = useState("");
  const [pageSize, setPageSize] = useState<"A4" | "A5">("A4");

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setTemplates(await api.listTemplates());
    } catch (cause) {
      setError(requestMessage(cause));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { void loadTemplates(); }, [loadTemplates]);

  const visibleTemplates = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return templates.filter((item) => {
      const matchesQuery = !normalizedQuery || item.template_key.toLowerCase().includes(normalizedQuery)
        || item.display_name.toLowerCase().includes(normalizedQuery);
      const matchesStatus = filter === "ALL"
        || (filter === "PUBLISHED" && item.status === "PUBLISHED")
        || (filter === "EDITABLE" && (isEditableTemplateStatus(item.status) || Boolean(item.active_draft)));
      return matchesQuery && matchesStatus;
    });
  }, [filter, query, templates]);

  async function createBlank() {
    if (!templateKey.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await onCreateBlank(
        templateKey.trim().toUpperCase(),
        pageSize,
        displayName.trim(),
        description.trim(),
      );
    } catch (cause) {
      setError(requestMessage(cause));
    } finally {
      setCreating(false);
    }
  }

  return <main className="template-center">
    <header className="template-center-header">
      <div><span className="eyebrow">模板中心</span><h1>纸质表单模板库</h1><p>选择已发布版本查看打印内容；调优始终复制为新的草稿版本。</p></div>
      <button className="text-button" onClick={onBack}>返回审核工作台</button>
    </header>
    {error && <div className="error-banner" role="alert"><span>{error}</span><button className="text-button" onClick={() => void loadTemplates()}>重试</button></div>}
    <section className="template-library-layout">
      <aside className="library-rail">
        <h2>模板库</h2>
        <label>搜索模板<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="名称或模板键" /></label>
        <div className="filter-chips" aria-label="模板状态筛选">
          {(["ALL", "PUBLISHED", "EDITABLE"] as const).map((status) => <button key={status} className={filter === status ? "active" : ""} onClick={() => setFilter(status)}>{statusLabel(status)}</button>)}
        </div>
        <div className="library-create">
          <h3>创建空白模板</h3>
          <label>模板名称<input value={displayName} maxLength={100} onChange={(event) => setDisplayName(event.target.value)} /></label>
          <label>模板键<input value={templateKey} onChange={(event) => setTemplateKey(event.target.value.toUpperCase())} /></label>
          <label>用途说明<textarea value={description} maxLength={500} onChange={(event) => setDescription(event.target.value)} /></label>
          <label>页面规格<select value={pageSize} onChange={(event) => setPageSize(event.target.value as "A4" | "A5")}><option>A4</option><option>A5</option></select></label>
          <button className="button button-primary" disabled={creating || !templateKey.trim() || !displayName.trim()} onClick={() => void createBlank()}>{creating ? "正在创建…" : "创建空白模板"}</button>
          <button className="button button-secondary" disabled>模板包导入将在安全 ZIP 导入 API 完成后开放</button>
        </div>
      </aside>
      <section className="template-library-content" aria-live="polite">
        <div className="library-summary"><strong>{loading ? "正在加载模板库…" : `共 ${visibleTemplates.length} 个模板`}</strong><span>模板数据来自已保存的版本记录</span></div>
        {!loading && !error && visibleTemplates.length === 0 && <div className="library-empty"><h2>还没有可显示的模板</h2><p>创建空白模板后，草稿会在这里显示；系统不会虚构已发布版本。</p></div>}
        <div className="template-card-grid">
          {visibleTemplates.map((item) => <TemplateCard key={item.template_key} api={api} item={item} onChanged={loadTemplates} onSelectPublished={onSelectPublished} onOpenDraft={onOpenDraft} />)}
        </div>
      </section>
    </section>
  </main>;
}

function TemplateCard({ api, item, onChanged, onSelectPublished, onOpenDraft }: { api: TemplateApi; item: TemplateLibraryItem; onChanged: () => Promise<void>; onSelectPublished: (id: string) => void; onOpenDraft: (id: string) => void }) {
  const published = item.status === "PUBLISHED";
  const viewable = ["PUBLISHED", "DEPRECATED", "RETIRED"].includes(item.status);
  const [editingMetadata, setEditingMetadata] = useState(false);
  const [name, setName] = useState(item.display_name);
  const [purpose, setPurpose] = useState(item.description);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function saveMetadata() {
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.updateMetadata(item.template_key, name.trim(), purpose.trim());
      setEditingMetadata(false);
      await onChanged();
    } catch (cause) {
      setError(requestMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function discardDraft(versionId: string) {
    if (!window.confirm("确定放弃这个草稿吗？草稿字段和未发布修改将被永久删除。")) return;
    setBusy(true);
    setError(null);
    try {
      await api.discardDraft(versionId);
      await onChanged();
    } catch (cause) {
      setError(requestMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function retire() {
    if (!window.confirm("确定退役此模板吗？历史表单和打印件会保留，但不能再用于新分类和打印。")) return;
    setBusy(true);
    setError(null);
    try {
      await api.retireTemplate(item.template_key);
      await onChanged();
    } catch (cause) {
      setError(requestMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return <article className="template-library-card">
    <div className="card-heading"><div><span className="eyebrow">{item.template_key}</span><h2>{item.display_name}</h2></div><span className={`status-pill ${published ? "success" : "warning"}`}>{published ? "已发布" : statusLabel(item.status)}</span></div>
    <p>{item.description || "尚未填写用途说明"}</p>
    {editingMetadata && <div className="template-metadata-editor">
      <label>模板名称<input value={name} maxLength={100} disabled={busy} onChange={(event) => setName(event.target.value)} /></label>
      <label>用途说明<textarea value={purpose} maxLength={500} disabled={busy} onChange={(event) => setPurpose(event.target.value)} /></label>
      <div><button className="button button-primary" disabled={busy || !name.trim()} onClick={() => void saveMetadata()}>保存信息</button><button className="button button-secondary" disabled={busy} onClick={() => setEditingMetadata(false)}>取消</button></div>
    </div>}
    {error && <p className="inline-warning">{error}</p>}
    <dl className="template-meta"><div><dt>页面</dt><dd>{pageLabel(item.page)}</dd></div><div><dt>当前发布版本</dt><dd>{item.current_published_version ? `V${item.current_published_version}` : "尚未发布"}</dd></div><div><dt>字段数</dt><dd>{item.field_count}</dd></div></dl>
    <div className="template-card-actions">
      {viewable ? <button className="button button-secondary" disabled={busy} onClick={() => onSelectPublished(item.version_id)}>查看只读预览</button> : isEditableTemplateStatus(item.status) && <button className="button button-secondary" disabled={busy} onClick={() => onOpenDraft(item.version_id)}>继续编辑草稿</button>}
      <button className="text-button" disabled={busy} onClick={() => setEditingMetadata((value) => !value)}>编辑名称与说明</button>
      {isEditableTemplateStatus(item.status) && <button className="text-button danger" disabled={busy} onClick={() => void discardDraft(item.version_id)}>放弃草稿</button>}
      {published && <button className="text-button danger" disabled={busy || Boolean(item.active_draft)} title={item.active_draft ? "请先放弃活动草稿" : undefined} onClick={() => void retire()}>退役模板</button>}
    </div>
    {item.active_draft && item.active_draft.version_id !== item.version_id && isEditableTemplateStatus(item.active_draft.status) && <div className="draft-resume"><span>可恢复草稿 V{item.active_draft.version} · {item.active_draft.field_count} 个字段 · {statusLabel(item.active_draft.status)}</span><button className="text-button" disabled={busy} onClick={() => onOpenDraft(item.active_draft!.version_id)}>继续编辑</button><button className="text-button danger" disabled={busy} onClick={() => void discardDraft(item.active_draft!.version_id)}>放弃草稿</button></div>}
  </article>;
}

function pageLabel(page: TemplatePage): string { return `${page.size} · ${page.orientation === "portrait" ? "纵向" : page.orientation}`; }
function statusLabel(status: StatusFilter | string): string { return ({ ALL: "全部", PUBLISHED: "已发布", EDITABLE: "可编辑草稿", DRAFT: "草稿", PREFLIGHT_FAILED: "预检失败", READY_TO_PUBLISH: "可发布", DEPRECATED: "已停用", RETIRED: "已退役" } as Record<string, string>)[status] ?? status; }
function requestMessage(cause: unknown): string { return cause instanceof Error ? cause.message : "模板请求无法完成。"; }
