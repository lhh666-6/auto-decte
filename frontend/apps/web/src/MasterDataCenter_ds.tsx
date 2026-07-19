import {
  ApiRequestError,
  MasterDataApi,
  type MasterDataAudit,
  type MasterDataCatalog,
  type MasterDataRecord,
} from "@form-detection/api-client";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  MASTER_DATA_FORM,
  attributesFromBusinessForm,
  businessFormFromRecord,
} from "./master-data-form";
import { ConfirmDialog } from "./ui/ConfirmDialog";
import { ProblemNotice } from "./ui/ProblemNotice";
import { TraceDetails } from "./ui/TraceDetails";
import { businessErrorMessage } from "./ui/business-errors";

const CATALOGS: Array<{ key: MasterDataCatalog; label: string; hint: string }> = [
  { key: "employees", label: "员工", hint: "员工编号、姓名、班组与岗位" },
  { key: "work-orders", label: "工单", hint: "生产工单及关联产品、计划数量" },
  { key: "products", label: "产品", hint: "产品编码、规格与计量单位" },
  { key: "processes", label: "工序", hint: "工序编码、顺序与工作站" },
];

interface MasterDataCenterProps {
  api?: MasterDataApi;
  initialCatalog?: MasterDataCatalog;
  onCatalogChange?: (catalog: MasterDataCatalog) => void;
}

export function MasterDataCenter({
  api,
  initialCatalog = "employees",
  onCatalogChange,
}: MasterDataCenterProps) {
  const client = useMemo(() => api ?? new MasterDataApi("/api/v1"), [api]);
  const [catalog, setCatalog] = useState<MasterDataCatalog>(initialCatalog);
  const [items, setItems] = useState<MasterDataRecord[]>([]);
  const [selected, setSelected] = useState<MasterDataRecord | null>(null);
  const [audits, setAudits] = useState<MasterDataAudit[]>([]);
  const [query, setQuery] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [creating, setCreating] = useState(false);
  const [code, setCode] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [businessValues, setBusinessValues] = useState<Record<string, string>>({});
  const [extraAttributesText, setExtraAttributesText] = useState("{}");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);

  const refresh = useCallback(async (nextCatalog = catalog) => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await client.list(nextCatalog, { includeInactive, query });
      setItems(loaded);
      setSelected((current) => {
        if (current?.catalog !== nextCatalog) return null;
        return loaded.find((item) => item.code === current.code) ?? null;
      });
    } catch (cause) {
      setError(toMessage(cause));
    } finally {
      setLoading(false);
    }
  }, [catalog, client, includeInactive, query]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (catalog === initialCatalog) return;
    setCatalog(initialCatalog);
    resetEditor();
    setQuery("");
  }, [initialCatalog]); // The URL owns the active directory.

  function resetEditor() {
    setSelected(null);
    setAudits([]);
    setCreating(false);
    setMessage(null);
    setError(null);
  }

  function chooseCatalog(next: MasterDataCatalog) {
    if (next === catalog) return;
    setCatalog(next);
    resetEditor();
    setQuery("");
    onCatalogChange?.(next);
  }

  async function chooseRecord(record: MasterDataRecord) {
    const mapped = businessFormFromRecord(record.catalog, record.attributes);
    setCreating(false);
    setSelected(record);
    setCode(record.code);
    setDisplayName(record.display_name);
    setBusinessValues(mapped.values);
    setExtraAttributesText(JSON.stringify(mapped.extra, null, 2));
    setReason("");
    setMessage(null);
    setError(null);
    setAudits(await client.audits(record.catalog, record.code).catch(() => []));
  }

  function startCreate() {
    const mapped = businessFormFromRecord(catalog, {});
    setCreating(true);
    setSelected(null);
    setAudits([]);
    setCode("");
    setDisplayName("");
    setBusinessValues(mapped.values);
    setExtraAttributesText("{}");
    setReason("");
    setMessage(null);
    setError(null);
  }

  async function save() {
    setError(null);
    setMessage(null);
    let extra: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(extraAttributesText || "{}");
      if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error("更多信息必须是 JSON 对象");
      }
      extra = parsed as Record<string, unknown>;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "更多信息格式无效");
      return;
    }
    if (!code.trim() || !displayName.trim() || !reason.trim()) {
      setError("编码、名称和变更原因均为必填项。");
      return;
    }
    const attributes = attributesFromBusinessForm(catalog, businessValues, extra);
    setLoading(true);
    try {
      const wasCreating = creating;
      const saved = wasCreating
        ? await client.create(catalog, {
          code: code.trim(),
          display_name: displayName.trim(),
          attributes,
          reason: reason.trim(),
        })
        : await client.update(catalog, selected!.code, {
          expected_revision: selected!.revision,
          display_name: displayName.trim(),
          attributes,
          reason: reason.trim(),
        });
      const mapped = businessFormFromRecord(catalog, saved.attributes);
      setCreating(false);
      setSelected(saved);
      setCode(saved.code);
      setDisplayName(saved.display_name);
      setBusinessValues(mapped.values);
      setExtraAttributesText(JSON.stringify(mapped.extra, null, 2));
      setReason("");
      setMessage(wasCreating ? "基础数据已创建。" : `已保存第 ${saved.revision} 版。`);
      setAudits(await client.audits(catalog, saved.code).catch(() => []));
      await refresh();
    } catch (cause) {
      setError(conflictMessage(cause));
      if (cause instanceof ApiRequestError && cause.code === "MASTER_DATA_REVISION_CONFLICT") {
        await refresh();
      }
    } finally {
      setLoading(false);
    }
  }

  async function changeActive() {
    if (!selected || !reason.trim()) {
      setError("停用或恢复前必须填写变更原因。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const saved = await client.setActive(
        catalog,
        selected.code,
        !selected.active,
        selected.revision,
        reason.trim(),
      );
      setSelected(saved);
      setReason("");
      setMessage(saved.active ? "该记录已恢复使用。" : "该记录已停用，默认列表和复核选项将不再显示。");
      setAudits(await client.audits(catalog, saved.code).catch(() => []));
      await refresh();
    } catch (cause) {
      setError(conflictMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  const meta = CATALOGS.find((item) => item.key === catalog)!;
  const form = MASTER_DATA_FORM[catalog];
  return (
    <main className="master-data-center">
      <header className="master-data-header">
        <div>
          <span className="eyebrow">基础数据</span>
          <h1>员工、工单、产品与工序</h1>
          <p>统一维护复核和模板下拉项使用的业务基础数据；编码不可改，记录只停用、不删除。</p>
        </div>
        <button type="button" className="button button-primary" onClick={startCreate}>新增{meta.label}</button>
      </header>

      <nav className="master-data-tabs" aria-label="基础数据类型">
        {CATALOGS.map((item) => (
          <button
            type="button"
            aria-label={item.label}
            className={item.key === catalog ? "active" : ""}
            key={item.key}
            onClick={() => chooseCatalog(item.key)}
          >
            <strong>{item.label}</strong><span>{item.hint}</span>
          </button>
        ))}
      </nav>

      {error ? <ProblemNotice title="基础数据没有保存" reason={error} actionLabel="返回并检查填写内容" onAction={() => setError(null)} /> : null}
      {message ? <div className="success-banner master-data-message" role="status">{message}</div> : null}

      <div className="master-data-layout">
        <section className="master-data-list-card">
          <form className="master-data-search" onSubmit={(event) => { event.preventDefault(); void refresh(); }}>
            <input aria-label="搜索基础数据" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按编码或名称搜索" />
            <button type="submit" className="button button-secondary">搜索</button>
          </form>
          <label className="master-data-checkbox">
            <input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />
            显示已停用记录
          </label>
          <div className="master-data-list" aria-busy={loading}>
            {items.length === 0 ? (
              <p className="master-data-empty">
                {loading ? "正在加载…" : query.trim() ? `没有找到匹配的${meta.label}` : `${meta.label}目录为空`}
              </p>
            ) : items.map((item) => (
              <button
                type="button"
                key={item.code}
                className={`${selected?.code === item.code ? "selected" : ""} ${item.active ? "" : "inactive"}`}
                onClick={() => void chooseRecord(item)}
              >
                <span><strong>{item.display_name}</strong><small>{item.code}</small></span>
                <em>{item.active ? `v${item.revision}` : "已停用"}</em>
              </button>
            ))}
          </div>
        </section>

        <section className="master-data-editor">
          {!creating && !selected ? (
            <div className="master-data-empty editor-empty">
              <h2>{meta.label}目录</h2>
              <p>从左侧选择记录进行维护，或新增一条记录。</p>
            </div>
          ) : (
            <>
              <div className="master-data-editor-heading">
                <div><span className="eyebrow">{creating ? "新建记录" : "维护记录"}</span><h2>{creating ? `新增${meta.label}` : selected!.display_name}</h2></div>
                {selected && <span className={selected.active ? "status-pill active" : "status-pill inactive"}>{selected.active ? "使用中" : "已停用"}</span>}
              </div>
              <div className="master-data-form">
                <label>{form.codeLabel}<input value={code} readOnly={!creating} onChange={(event) => setCode(event.target.value)} placeholder="唯一且创建后不可修改" /></label>
                <label>{form.nameLabel}<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
                {form.fields.map((field) => (
                  <label key={field.key}>{field.label}<input type={field.type ?? "text"} value={businessValues[field.key] ?? ""} onChange={(event) => setBusinessValues((current) => ({ ...current, [field.key]: event.target.value }))} /></label>
                ))}
                <label className="wide">更多信息<textarea value={extraAttributesText} onChange={(event) => setExtraAttributesText(event.target.value)} spellCheck={false} placeholder="未列出的附加属性（JSON 对象）" /></label>
                <label className="wide">变更原因<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="用于不可篡改的审计记录" /></label>
              </div>
              <div className="master-data-actions">
                <button type="button" className="button button-primary" disabled={loading} onClick={() => void save()}>{creating ? "创建记录" : "保存新版本"}</button>
                {selected && <button type="button" className={`button ${selected.active ? "button-danger" : "button-secondary"}`} disabled={loading} onClick={() => selected.active ? setConfirmDeactivate(true) : void changeActive()}>{selected.active ? "停用基础数据" : "恢复使用"}</button>}
              </div>
              {selected && (
                <>
                  <TraceDetails items={[{ label: "当前修订版本", value: String(selected.revision) }]} />
                  <section className="master-data-audit">
                    <h3>变更轨迹</h3>
                    {audits.length === 0 ? <p>暂无审计记录。</p> : <ol>{audits.map((audit) => <li key={audit.audit_id}><strong>{audit.event_type}</strong><span>版本 {audit.revision} · {audit.actor_id} · {new Date(audit.timestamp).toLocaleString()}</span><p>{audit.reason}</p></li>)}</ol>}
                  </section>
                </>
              )}
            </>
          )}
        </section>
      </div>
      {confirmDeactivate && selected ? (
        <ConfirmDialog
          title="停用当前基础数据"
          description="停用后不会删除历史记录，但默认列表、审核选项和新模板引用将不再显示它。"
          confirmLabel="确认停用基础数据"
          cancelLabel="取消停用"
          loading={loading}
          confirmDisabled={!reason.trim()}
          onCancel={() => setConfirmDeactivate(false)}
          onConfirm={() => {
            setConfirmDeactivate(false);
            void changeActive();
          }}
        />
      ) : null}
    </main>
  );
}

function toMessage(cause: unknown): string {
  return businessErrorMessage(cause, "基础数据请求无法完成。");
}

function conflictMessage(cause: unknown): string {
  if (cause instanceof ApiRequestError && cause.code === "MASTER_DATA_REVISION_CONFLICT") {
    return "该记录已被其他人修改，请刷新后重试";
  }
  if (cause instanceof ApiRequestError && cause.code === "PERMISSION_DENIED") {
    return businessErrorMessage(cause, "基础数据请求无法完成。");
  }
  return toMessage(cause);
}
