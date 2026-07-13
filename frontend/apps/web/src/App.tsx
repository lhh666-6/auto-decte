import {
  ApiRequestError,
  ReviewWorkbenchApi,
  type RecognitionCandidate,
  type ReviewField,
  type ReviewHistory,
  type ReviewLease,
  type WorkbenchDetail,
} from "@form-detection/api-client";
import { WebNotificationPort } from "@form-detection/shell-ports";
import { useCallback, useEffect, useMemo, useState } from "react";

import { buildConfirmValues } from "./review-model";
import { TemplateStudio } from "./TemplateStudio_ds";

const notificationPort = new WebNotificationPort();

type MobilePane = "evidence" | "fields";
type Feature = "review" | "templates";

function stringValue(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function sourceDimension(region: Record<string, number>, longName: "width" | "height"): number {
  return region[longName] ?? region[longName === "width" ? "w" : "h"] ?? 0;
}

export function App() {
  const api = useMemo(() => new ReviewWorkbenchApi("/api/v1"), []);
  const [formIdInput, setFormIdInput] = useState("FORM-1");
  const [detail, setDetail] = useState<WorkbenchDetail | null>(null);
  const [history, setHistory] = useState<ReviewHistory | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, unknown>>({});
  const [lease, setLease] = useState<ReviewLease | null>(null);
  const [imageSize, setImageSize] = useState({ width: 1, height: 1 });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [mobilePane, setMobilePane] = useState<MobilePane>("evidence");
  const [feature, setFeature] = useState<Feature>("review");

  const selectedField = detail?.fields.find((field) => field.field_id === selectedFieldId) ?? null;
  const originalEvidence = detail?.evidence.find((item) => item.type === "ORIGINAL_IMAGE") ?? null;
  const warningCount = detail?.fields.filter((field) => {
    const best = field.candidates[0];
    return !field.current_value || (best !== undefined && best.confidence < 0.8);
  }).length ?? 0;

  const loadWorkbench = useCallback(async () => {
    const formId = formIdInput.trim();
    if (!formId) {
      setError("请先输入表单编号。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [loadedDetail, loadedHistory] = await Promise.all([
        api.getWorkbench(formId),
        api.getHistory(formId).catch(() => null),
      ]);
      setDetail(loadedDetail);
      setHistory(loadedHistory);
      setEdits({});
      setSelectedFieldId(loadedDetail.fields[0]?.field_id ?? null);
      setLease(null);
    } catch (cause) {
      setDetail(null);
      setHistory(null);
      setError(toMessage(cause));
    } finally {
      setLoading(false);
    }
  }, [api, formIdInput]);

  useEffect(() => {
    if (!detail || !lease) return undefined;
    const timer = window.setInterval(() => {
      void api.heartbeatLease(detail.form.form_id, lease.lease_token).then(setLease).catch((cause) => {
        setLease(null);
        setError(`审核锁已失效：${toMessage(cause)}`);
      });
    }, 120_000);
    return () => window.clearInterval(timer);
  }, [api, detail, lease]);

  async function acquireLease() {
    if (!detail) return;
    try {
      setError(null);
      setLease(await api.acquireLease(detail.form.form_id));
    } catch (cause) {
      setError(toMessage(cause));
    }
  }

  async function releaseLease() {
    if (!detail || !lease) return;
    try {
      await api.releaseLease(detail.form.form_id, lease.lease_token);
      setLease(null);
    } catch (cause) {
      setError(toMessage(cause));
    }
  }

  async function confirmAndNext() {
    if (!detail) return;
    if (!lease) {
      setError("请先获取审核锁，再确认表单。");
      return;
    }
    try {
      setLoading(true);
      const values = buildConfirmValues(
        detail.fields.map((field) => ({ fieldId: field.field_id, currentValue: field.current_value })),
        edits,
      );
      await api.confirm(detail.form.form_id, {
        expectedVersion: detail.form.current_record_version,
        leaseToken: lease.lease_token,
        values,
        reason: "人工审核工作台确认",
        evidenceIds: detail.evidence.map((evidence) => evidence.file_id),
      });
      await notificationPort.notify({
        title: "表单已确认",
        body: `${detail.form.form_id} 已写入新版本。`,
        level: "success",
        timeoutMs: 3_500,
      });
      await loadWorkbench();
    } catch (cause) {
      setError(toMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  function selectField(field: ReviewField) {
    setSelectedFieldId(field.field_id);
    setMobilePane("fields");
  }

  function useCandidate(fieldId: string, candidate: RecognitionCandidate) {
    setEdits((current) => ({ ...current, [fieldId]: candidate.candidate_value }));
  }

  if (feature === "templates") return <TemplateStudio onBack={() => setFeature("review")} />;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">▦</span> 产量采集工作台</div>
        <div className="topbar-context">人工审核 <span className="connection-dot" /> 本地服务</div>
      </header>

      <aside className="queue-sidebar" aria-label="工作队列">
        <div className="queue-title">审核队列</div>
        <nav>
          <QueueItem label="待分类" count="—" />
          <QueueItem label="待复核" count="—" active />
          <QueueItem label="规则异常" count={detail ? String(warningCount) : "—"} warning />
          <QueueItem label="可导出" count="—" />
        </nav>
        <div className="sidebar-divider" />
        <nav className="secondary-nav">
          <button type="button">数据管理</button>
          <button type="button" onClick={() => setFeature("templates")}>模板与字段</button>
          <button type="button">员工 / 工单</button>
          <button type="button">产品 / 工序</button>
        </nav>
      </aside>

      <main className="workbench">
        <section className="context-card">
          <form
            className="form-loader"
            onSubmit={(event) => {
              event.preventDefault();
              void loadWorkbench();
            }}
          >
            <label htmlFor="form-id">表单编号</label>
            <input
              id="form-id"
              value={formIdInput}
              onChange={(event) => setFormIdInput(event.target.value)}
              placeholder="例如 FORM-1"
            />
            <button type="submit" className="button button-secondary" disabled={loading}>加载表单</button>
          </form>
          <div className="form-summary">
            <strong>{detail?.form.form_id ?? "未加载表单"}</strong>
            <span>{detail ? `模板 ${detail.form.template_id} · v${detail.form.template_version}` : "输入编号后加载"}</span>
          </div>
          <div className="lease-summary">
            {lease ? <span className="lease-active">审核锁有效至 {new Date(lease.expires_at).toLocaleTimeString()}</span> : <span>未获取审核锁</span>}
            {lease ? (
              <button type="button" className="text-button" onClick={() => void releaseLease()}>释放</button>
            ) : (
              <button type="button" className="text-button" disabled={!detail} onClick={() => void acquireLease()}>获取审核锁</button>
            )}
          </div>
        </section>

        {error && <div className="error-banner" role="alert">{error}</div>}

        <div className="mobile-pane-switch" role="tablist" aria-label="审核面板">
          <button type="button" className={mobilePane === "evidence" ? "active" : ""} onClick={() => setMobilePane("evidence")}>图片</button>
          <button type="button" className={mobilePane === "fields" ? "active" : ""} onClick={() => setMobilePane("fields")}>电子表格</button>
        </div>

        <section className="review-grid" data-mobile-pane={mobilePane}>
          <EvidenceCanvas
            evidenceUrl={originalEvidence?.download_url ?? null}
            fields={detail?.fields ?? []}
            selectedFieldId={selectedFieldId}
            imageSize={imageSize}
            onImageLoad={setImageSize}
            onSelectField={selectField}
          />
          <FieldTable
            fields={detail?.fields ?? []}
            edits={edits}
            selectedFieldId={selectedFieldId}
            onSelectField={selectField}
            onEdit={(fieldId, value) => setEdits((current) => ({ ...current, [fieldId]: value }))}
          />
        </section>

        <section className="detail-drawer">
          <div className="drawer-heading">
            <div>
              <span className="eyebrow">规则与建议</span>
              <strong>{selectedField ? selectedField.field_name : "选择一个字段查看详情"}</strong>
            </div>
            <span className={warningCount > 0 ? "status-pill warning" : "status-pill success"}>
              {warningCount > 0 ? `${warningCount} 项待确认` : "无待确认项"}
            </span>
          </div>
          <div className="drawer-columns">
            <div>
              <span className="drawer-label">识别候选</span>
              {selectedField?.candidates.length ? selectedField.candidates.map((candidate) => (
                <button key={candidate.attempt_id} type="button" className="candidate-chip" onClick={() => useCandidate(selectedField.field_id, candidate)}>
                  {stringValue(candidate.candidate_value)} <span>{Math.round(candidate.confidence * 100)}%</span>
                </button>
              )) : <span className="muted">暂无 OCR/OMR 候选</span>}
            </div>
            <div>
              <span className="drawer-label">历史版本</span>
              <span className="muted">{history?.versions.length ?? 0} 个版本 · {history?.audits.length ?? 0} 条审计事件</span>
            </div>
            <div>
              <span className="drawer-label">证据</span>
              <span className="muted">{detail?.evidence.length ?? 0} 个受控文件</span>
            </div>
          </div>
        </section>

        <footer className="action-bar">
          <button type="button" className="button button-secondary" disabled>保存草稿</button>
          <span className="action-hint">确认会创建新版本并写入审计记录</span>
          <button type="button" className="button button-primary" disabled={!detail || loading} onClick={() => void confirmAndNext()}>
            确认并下一张
          </button>
        </footer>
      </main>
    </div>
  );
}

function QueueItem({ label, count, active = false, warning = false }: { label: string; count: string; active?: boolean; warning?: boolean }) {
  return <button type="button" className={`queue-item ${active ? "active" : ""} ${warning ? "warning" : ""}`}><span>{label}</span><span>{count}</span></button>;
}

function EvidenceCanvas({
  evidenceUrl,
  fields,
  selectedFieldId,
  imageSize,
  onImageLoad,
  onSelectField,
}: {
  evidenceUrl: string | null;
  fields: ReviewField[];
  selectedFieldId: string | null;
  imageSize: { width: number; height: number };
  onImageLoad: (size: { width: number; height: number }) => void;
  onSelectField: (field: ReviewField) => void;
}) {
  return (
    <section className="evidence-panel" aria-label="原始表单证据">
      <div className="panel-toolbar"><strong>原始表单证据</strong><span>适配 · 100% · 旋转</span></div>
      <div className="canvas-stage">
        {evidenceUrl ? (
          <div className="image-wrap">
            <img src={evidenceUrl} alt="原始表单" onLoad={(event) => onImageLoad({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} />
            {fields.map((field) => {
              const region = field.source_region;
              const width = sourceDimension(region, "width");
              const height = sourceDimension(region, "height");
              return (
                <button
                  key={field.field_id}
                  type="button"
                  className={`field-overlay ${field.field_id === selectedFieldId ? "selected" : ""}`}
                  style={{
                    left: `${(region.x / imageSize.width) * 100}%`,
                    top: `${(region.y / imageSize.height) * 100}%`,
                    width: `${(width / imageSize.width) * 100}%`,
                    height: `${(height / imageSize.height) * 100}%`,
                  }}
                  onClick={() => onSelectField(field)}
                  aria-label={`定位字段 ${field.field_name}`}
                >
                  <span>{field.field_name}</span>
                </button>
              );
            })}
          </div>
        ) : <div className="empty-canvas">加载表单后在此显示原始证据与字段框</div>}
      </div>
    </section>
  );
}

function FieldTable({
  fields,
  edits,
  selectedFieldId,
  onSelectField,
  onEdit,
}: {
  fields: ReviewField[];
  edits: Record<string, unknown>;
  selectedFieldId: string | null;
  onSelectField: (field: ReviewField) => void;
  onEdit: (fieldId: string, value: string) => void;
}) {
  return (
    <section className="field-panel" aria-label="可编辑电子表格">
      <div className="panel-toolbar"><strong>电子表格</strong><span>{fields.length} 个字段</span></div>
      <div className="field-table" role="table">
        <div className="field-row field-head" role="row"><span>字段</span><span>识别结果</span><span>置信度</span><span>确认值</span><span>状态</span></div>
        {fields.length === 0 ? <div className="table-empty">尚未加载字段</div> : fields.map((field) => {
          const candidate = field.candidates[0];
          const displayValue = Object.hasOwn(edits, field.field_id) ? edits[field.field_id] : field.current_value;
          const hasWarning = !displayValue || (candidate !== undefined && candidate.confidence < 0.8);
          return (
            <div
              className={`field-row ${field.field_id === selectedFieldId ? "selected" : ""} ${hasWarning ? "has-warning" : ""}`}
              key={field.field_id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectField(field)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") onSelectField(field);
              }}
            >
              <span className="field-name">{field.field_name}</span>
              <span className="candidate-value">{candidate ? stringValue(candidate.candidate_value) : "—"}</span>
              <span>{candidate ? `${Math.round(candidate.confidence * 100)}%` : "—"}</span>
              <span onClick={(event) => event.stopPropagation()}><input aria-label={`${field.field_name} 确认值`} value={stringValue(displayValue)} onChange={(event) => onEdit(field.field_id, event.target.value)} /></span>
              <span>{hasWarning ? <em className="inline-warning">待确认</em> : <em className="inline-success">已就绪</em>}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function toMessage(cause: unknown): string {
  if (cause instanceof ApiRequestError) return `${cause.code}：${cause.message}`;
  return cause instanceof Error ? cause.message : "请求无法完成。";
}
