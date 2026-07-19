import { isEditableTemplateStatus, type TemplateApi, type TemplateLibraryItem, type TemplatePage } from "@form-detection/api-client";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ConfirmDialog } from "./ui/ConfirmDialog";
import { ProblemNotice } from "./ui/ProblemNotice";
import { getTemplateStatusCopy } from "./ui/business-language";

type Props = {
  api: TemplateApi;
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

export function TemplateLibrary({ api, onSelectPublished, onOpenDraft, onCreateBlank }: Props) {
  const [templates, setTemplates] = useState<TemplateLibraryItem[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<StatusFilter>("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

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

  return (
    <main className="template-center">
      <header className="template-center-header">
        <div><span className="eyebrow">模板中心</span><h1>纸质表单模板库</h1><p>选择已发布版本查看打印内容；调优始终复制为新的草稿版本。</p></div>
      </header>

      <section
        className="template-library-toolbar"
        aria-label="模板库工具栏"
        style={{ display: "flex", flexWrap: "wrap", alignItems: "end", gap: 12, maxWidth: 1280, margin: "0 auto 16px", padding: 16, border: "1px solid #d7dee8", borderRadius: 10, background: "white" }}
      >
        <label style={{ display: "grid", gap: 5, minWidth: 260, flex: 1 }}>搜索模板<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="名称或模板编号" /></label>
        <div className="filter-chips" aria-label="模板状态筛选">
          {(["ALL", "PUBLISHED", "EDITABLE"] as const).map((status) => (
            <button key={status} className={filter === status ? "active" : ""} onClick={() => setFilter(status)}>{statusLabel(status)}</button>
          ))}
        </div>
        <button className="button button-secondary" disabled>导入模板包（暂未开放）</button>
        <button className="button button-primary" onClick={() => setShowCreate(true)}>创建模板</button>
      </section>

      {error && <ProblemNotice title="模板库没有加载完成" reason={error} actionLabel="重新加载模板" onAction={() => void loadTemplates()} />}
      <section className="template-library-content" aria-live="polite">
        <div className="library-summary"><strong>{loading ? "正在加载模板库…" : `共 ${visibleTemplates.length} 个模板`}</strong><span>模板数据来自已保存的版本记录</span></div>
        {!loading && !error && visibleTemplates.length === 0 && <div className="library-empty"><h2>还没有可显示的模板</h2><p>创建空白模板后，草稿会在这里显示；系统不会虚构已发布版本。</p></div>}
        <div className="template-card-grid">
          {visibleTemplates.map((item) => (
            <TemplateCard key={item.template_key} api={api} item={item} onChanged={loadTemplates} onSelectPublished={onSelectPublished} onOpenDraft={onOpenDraft} />
          ))}
        </div>
      </section>

      {showCreate ? (
        <CreateTemplateDialog
          onCancel={() => setShowCreate(false)}
          onCreate={async (...input) => {
            await onCreateBlank(...input);
            setShowCreate(false);
          }}
        />
      ) : null}
    </main>
  );
}

function CreateTemplateDialog({ onCancel, onCreate }: {
  onCancel(): void;
  onCreate(templateKey: string, pageSize: "A4" | "A5", displayName: string, description: string): Promise<void>;
}) {
  const [templateKey, setTemplateKey] = useState("NEW_TEMPLATE");
  const [displayName, setDisplayName] = useState("新建模板");
  const [description, setDescription] = useState("");
  const [pageSize, setPageSize] = useState<"A4" | "A5">("A4");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    if (!templateKey.trim() || !displayName.trim()) return;
    setCreating(true);
    setError("");
    try {
      await onCreate(templateKey.trim().toUpperCase(), pageSize, displayName.trim(), description.trim());
    } catch (cause) {
      setError(requestMessage(cause));
      setCreating(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="review-action-dialog" role="dialog" aria-modal="true" aria-label="创建模板">
        <h2>创建模板</h2>
        <label>模板名称<input value={displayName} maxLength={100} onChange={(event) => setDisplayName(event.target.value)} /></label>
        <label>模板编号<input value={templateKey} onChange={(event) => setTemplateKey(event.target.value.toUpperCase())} /></label>
        <label>用途说明<textarea value={description} maxLength={500} onChange={(event) => setDescription(event.target.value)} /></label>
        <label>页面规格<select value={pageSize} onChange={(event) => setPageSize(event.target.value as "A4" | "A5")}><option>A4</option><option>A5</option></select></label>
        {error ? <p className="inline-warning">{error}</p> : null}
        <div className="dialog-actions">
          <button className="button button-secondary" disabled={creating} onClick={onCancel}>取消</button>
          <button className="button button-primary" disabled={creating || !templateKey.trim() || !displayName.trim()} onClick={() => void submit()}>{creating ? "正在创建…" : "创建空白模板"}</button>
        </div>
      </section>
    </div>
  );
}

function TemplateCard({ api, item, onChanged, onSelectPublished, onOpenDraft }: {
  api: TemplateApi;
  item: TemplateLibraryItem;
  onChanged: () => Promise<void>;
  onSelectPublished: (id: string) => void;
  onOpenDraft: (id: string) => void;
}) {
  const published = item.status === "PUBLISHED";
  const viewable = ["PUBLISHED", "DEPRECATED", "RETIRED"].includes(item.status);
  const [showMore, setShowMore] = useState(false);
  const [editingMetadata, setEditingMetadata] = useState(false);
  const [name, setName] = useState(item.display_name);
  const [purpose, setPurpose] = useState(item.description);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<{ kind: "discard"; versionId: string } | { kind: "retire" } | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try { await action(); } catch (cause) { setError(requestMessage(cause)); } finally { setBusy(false); }
  }

  async function discardDraft(versionId: string) {
    await run(async () => { await api.discardDraft(versionId); await onChanged(); });
  }

  async function retire() {
    await run(async () => { await api.retireTemplate(item.template_key); await onChanged(); });
  }

  return (
    <article className="template-library-card">
      <div className="card-heading">
        <div><h2>{item.display_name}</h2><span className="eyebrow">{item.template_key}</span></div>
        <span className={`status-pill ${published ? "success" : "warning"}`}>{published ? "已发布" : statusLabel(item.status)}</span>
      </div>
      <p>{item.description || "尚未填写用途说明"}</p>
      {error && <p className="inline-warning">{error}</p>}
      <dl className="template-meta"><div><dt>页面</dt><dd>{pageLabel(item.page)}</dd></div><div><dt>当前发布版本</dt><dd>{item.current_published_version ? `V${item.current_published_version}` : "尚未发布"}</dd></div><div><dt>字段数</dt><dd>{item.field_count}</dd></div></dl>
      <div className="template-card-actions">
        {viewable ? (
          <button className="button button-secondary" disabled={busy} onClick={() => onSelectPublished(item.version_id)}>查看模板</button>
        ) : (
          <button className="button button-secondary" disabled={busy} onClick={() => onOpenDraft(item.version_id)}>继续编辑</button>
        )}
        <button className="text-button" aria-expanded={showMore} onClick={() => setShowMore((value) => !value)}>更多</button>
      </div>
      {showMore ? (
        <div className="template-card-more">
          <button className="text-button" disabled={busy} onClick={() => setEditingMetadata((value) => !value)}>编辑名称与说明</button>
          {isEditableTemplateStatus(item.status) ? <button className="text-button danger" disabled={busy} onClick={() => setPendingAction({ kind: "discard", versionId: item.version_id })}>放弃草稿</button> : null}
          {published ? <button className="text-button danger" disabled={busy || Boolean(item.active_draft)} onClick={() => setPendingAction({ kind: "retire" })}>退役模板</button> : null}
          {item.active_draft ? <button className="text-button" onClick={() => onOpenDraft(item.active_draft!.version_id)}>继续编辑草稿 V{item.active_draft.version}</button> : null}
        </div>
      ) : null}
      {editingMetadata ? (
        <div className="template-metadata-editor">
          <label>模板名称<input value={name} maxLength={100} disabled={busy} onChange={(event) => setName(event.target.value)} /></label>
          <label>用途说明<textarea value={purpose} maxLength={500} disabled={busy} onChange={(event) => setPurpose(event.target.value)} /></label>
          <div><button className="button button-primary" disabled={busy || !name.trim()} onClick={() => void run(async () => { await api.updateMetadata(item.template_key, name.trim(), purpose.trim()); setEditingMetadata(false); await onChanged(); })}>保存信息</button><button className="button button-secondary" onClick={() => setEditingMetadata(false)}>取消</button></div>
        </div>
      ) : null}
      {pendingAction ? (
        <ConfirmDialog
          title={pendingAction.kind === "discard" ? "放弃当前模板草稿" : "退役当前模板"}
          description={pendingAction.kind === "discard" ? "草稿字段和未发布修改将被永久删除。" : "历史表单和打印件会保留，但该模板不能再用于新分类和打印。"}
          confirmLabel={pendingAction.kind === "discard" ? "确认放弃模板草稿" : "确认退役模板"}
          cancelLabel="取消操作"
          loading={busy}
          onCancel={() => setPendingAction(null)}
          onConfirm={() => {
            const action = pendingAction;
            setPendingAction(null);
            if (action.kind === "discard") void discardDraft(action.versionId);
            else void retire();
          }}
        />
      ) : null}
    </article>
  );
}

function pageLabel(page: TemplatePage): string { return `${page.size} · ${page.orientation === "portrait" ? "纵向" : page.orientation}`; }
function statusLabel(status: StatusFilter | string): string {
  if (status === "ALL") return "全部";
  if (status === "EDITABLE") return "可编辑草稿";
  return getTemplateStatusCopy(status).label;
}
function requestMessage(cause: unknown): string { return cause instanceof Error ? cause.message : "模板请求无法完成。"; }
