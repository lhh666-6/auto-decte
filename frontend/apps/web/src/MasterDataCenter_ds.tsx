import {
  ApiRequestError,
  MasterDataApi,
  type MasterDataAudit,
  type MasterDataCatalog,
  type MasterDataRecord,
} from "@form-detection/api-client";
import { useCallback, useEffect, useMemo, useState } from "react";

const CATALOGS: Array<{ key: MasterDataCatalog; label: string; hint: string }> = [
  { key: "employees", label: "员工", hint: "员工编号、姓名、班组与岗位" },
  { key: "work-orders", label: "工单", hint: "生产工单及关联产品、计划数量" },
  { key: "products", label: "产品", hint: "产品编码、规格与计量单位" },
  { key: "processes", label: "工序", hint: "工序编码、顺序与工作站" },
];

export function MasterDataCenter({ onBack }: { onBack: () => void }) {
  const api = useMemo(() => new MasterDataApi("/api/v1"), []);
  const [catalog, setCatalog] = useState<MasterDataCatalog>("employees");
  const [items, setItems] = useState<MasterDataRecord[]>([]);
  const [selected, setSelected] = useState<MasterDataRecord | null>(null);
  const [audits, setAudits] = useState<MasterDataAudit[]>([]);
  const [query, setQuery] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [creating, setCreating] = useState(false);
  const [code, setCode] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [attributesText, setAttributesText] = useState("{}");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (nextCatalog = catalog) => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await api.list(nextCatalog, { includeInactive, query });
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
  }, [api, catalog, includeInactive, query]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function chooseCatalog(next: MasterDataCatalog) {
    setCatalog(next);
    setSelected(null);
    setAudits([]);
    setCreating(false);
    setQuery("");
    setMessage(null);
    setError(null);
  }

  async function chooseRecord(record: MasterDataRecord) {
    setCreating(false);
    setSelected(record);
    setCode(record.code);
    setDisplayName(record.display_name);
    setAttributesText(JSON.stringify(record.attributes, null, 2));
    setReason("");
    setMessage(null);
    setError(null);
    setAudits(await api.audits(record.catalog, record.code).catch(() => []));
  }

  function startCreate() {
    setCreating(true);
    setSelected(null);
    setAudits([]);
    setCode("");
    setDisplayName("");
    setAttributesText("{}");
    setReason("");
    setMessage(null);
    setError(null);
  }

  async function save() {
    setError(null);
    setMessage(null);
    let attributes: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(attributesText || "{}");
      if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error("属性必须是 JSON 对象");
      }
      attributes = parsed as Record<string, unknown>;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "属性 JSON 无效");
      return;
    }
    if (!code.trim() || !displayName.trim() || !reason.trim()) {
      setError("编码、名称和变更原因均为必填项。");
      return;
    }
    setLoading(true);
    try {
      const saved = creating
        ? await api.create(catalog, {
          code: code.trim(),
          display_name: displayName.trim(),
          attributes,
          reason: reason.trim(),
        })
        : await api.update(catalog, selected!.code, {
          expected_revision: selected!.revision,
          display_name: displayName.trim(),
          attributes,
          reason: reason.trim(),
        });
      setCreating(false);
      setSelected(saved);
      setCode(saved.code);
      setDisplayName(saved.display_name);
      setAttributesText(JSON.stringify(saved.attributes, null, 2));
      setReason("");
      setMessage(creating ? "主数据已创建。" : `已保存第 ${saved.revision} 版。`);
      setAudits(await api.audits(catalog, saved.code).catch(() => []));
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
      const saved = await api.setActive(
        catalog,
        selected.code,
        !selected.active,
        selected.revision,
        reason.trim(),
      );
      setSelected(saved);
      setReason("");
      setMessage(saved.active ? "该记录已恢复使用。" : "该记录已停用，默认列表和复核选项将不再显示。 ");
      setAudits(await api.audits(catalog, saved.code).catch(() => []));
      await refresh();
    } catch (cause) {
      setError(conflictMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  const meta = CATALOGS.find((item) => item.key === catalog)!;
  return (
    <main className="master-data-center">
      <header className="master-data-header">
        <div>
          <button type="button" className="text-button" onClick={onBack}>← 返回审核工作台</button>
          <span className="eyebrow">主数据中心</span>
          <h1>员工、工单、产品与工序</h1>
          <p>统一维护复核和模板下拉项使用的业务基础数据；编码不可改，记录只停用、不删除。</p>
        </div>
        <button type="button" className="button button-primary" onClick={startCreate}>新增{meta.label}</button>
      </header>

      <nav className="master-data-tabs" aria-label="主数据类型">
        {CATALOGS.map((item) => (
          <button
            type="button"
            className={item.key === catalog ? "active" : ""}
            key={item.key}
            onClick={() => chooseCatalog(item.key)}
          >
            <strong>{item.label}</strong><span>{item.hint}</span>
          </button>
        ))}
      </nav>

      {(error || message) && (
        <div className={error ? "error-banner master-data-message" : "success-banner master-data-message"} role="status">
          {error ?? message}
        </div>
      )}

      <div className="master-data-layout">
        <section className="master-data-list-card">
          <form className="master-data-search" onSubmit={(event) => { event.preventDefault(); void refresh(); }}>
            <input aria-label="搜索主数据" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按编码或名称搜索" />
            <button type="submit" className="button button-secondary">搜索</button>
          </form>
          <label className="master-data-checkbox">
            <input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />
            显示已停用记录
          </label>
          <div className="master-data-list" aria-busy={loading}>
            {items.length === 0 ? <p className="master-data-empty">{loading ? "正在加载…" : "暂无匹配记录"}</p> : items.map((item) => (
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
                <div><span className="eyebrow">{creating ? "新建记录" : `修订 v${selected!.revision}`}</span><h2>{creating ? `新增${meta.label}` : selected!.display_name}</h2></div>
                {selected && <span className={selected.active ? "status-pill active" : "status-pill inactive"}>{selected.active ? "使用中" : "已停用"}</span>}
              </div>
              <div className="master-data-form">
                <label>编码<input value={code} readOnly={!creating} onChange={(event) => setCode(event.target.value)} placeholder="唯一且创建后不可修改" /></label>
                <label>显示名称<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
                <label className="wide">扩展属性（JSON 对象）<textarea value={attributesText} onChange={(event) => setAttributesText(event.target.value)} spellCheck={false} /></label>
                <label className="wide">变更原因<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="用于不可篡改的审计记录" /></label>
              </div>
              <div className="master-data-actions">
                <button type="button" className="button button-primary" disabled={loading} onClick={() => void save()}>{creating ? "创建记录" : "保存新版本"}</button>
                {selected && <button type="button" className={`button ${selected.active ? "button-danger" : "button-secondary"}`} disabled={loading} onClick={() => void changeActive()}>{selected.active ? "停用记录" : "恢复使用"}</button>}
              </div>
              {selected && (
                <section className="master-data-audit">
                  <h3>变更轨迹</h3>
                  {audits.length === 0 ? <p>当前身份无审计读取权限，或暂无轨迹。</p> : <ol>{audits.map((audit) => <li key={audit.audit_id}><strong>{audit.event_type}</strong><span>v{audit.revision} · {audit.actor_id} · {new Date(audit.timestamp).toLocaleString()}</span><p>{audit.reason}</p></li>)}</ol>}
                </section>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

function toMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : "主数据请求失败。";
}

function conflictMessage(cause: unknown): string {
  if (cause instanceof ApiRequestError && cause.code === "MASTER_DATA_REVISION_CONFLICT") {
    return "该记录已被其他人更新，列表已刷新；请重新选择后再修改。";
  }
  if (cause instanceof ApiRequestError && cause.code === "PERMISSION_DENIED") {
    return "当前身份只有读取权限；主数据写入需要管理员权限。";
  }
  return toMessage(cause);
}
