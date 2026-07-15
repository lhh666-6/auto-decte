import {
  ApiRequestError,
  ReviewWorkbenchApi,
  type ClassificationOption,
  type RecognitionCandidate,
  type ReviewField,
  type ReviewHistory,
  type ReviewLease,
  type WorkbenchDetail,
} from "@form-detection/api-client";
import { WebNotificationPort } from "@form-detection/shell-ports";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  buildConfirmValues,
  reviewValueIssue,
  selectReviewEvidence,
} from "./review-model";
import { TemplateStudio } from "./TemplateStudio_ds";

const notificationPort = new WebNotificationPort();

type MobilePane = "evidence" | "fields";
type Feature = "review" | "templates" | "master-data";
type QueueKey = "classification" | "review" | "exceptions" | "exportable";
type ReviewAction = "return" | "void";

interface DuplicateImportInfo {
  code: "DUPLICATE_EVIDENCE";
  detail: string;
  existing_form: { form_id: string; review_status: string };
  actions: {
    can_open: boolean;
    can_reopen_for_test: boolean;
    can_purge_for_test: boolean;
  };
}

const QUEUES: Array<{ key: QueueKey; label: string; warning?: boolean }> = [
  { key: "classification", label: "待分类" },
  { key: "review", label: "待复核" },
  { key: "exceptions", label: "规则异常", warning: true },
  { key: "exportable", label: "可导出" },
];

function stringValue(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function sourceDimension(region: Record<string, number>, longName: "width" | "height"): number {
  return region[longName] ?? region[longName === "width" ? "w" : "h"] ?? 0;
}

export function App() {
  const api = useMemo(() => new ReviewWorkbenchApi("/api/v1"), []);
  const [formIdInput, setFormIdInput] = useState("");
  const [detail, setDetail] = useState<WorkbenchDetail | null>(null);
  const [history, setHistory] = useState<ReviewHistory | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, unknown>>({});
  const [ruleFailures, setRuleFailures] = useState<Record<string, string>>({});
  const [lease, setLease] = useState<ReviewLease | null>(null);
  const [imageSize, setImageSize] = useState({ width: 1, height: 1 });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [duplicateImport, setDuplicateImport] = useState<DuplicateImportInfo | null>(null);
  const [mobilePane, setMobilePane] = useState<MobilePane>("evidence");
  const [feature, setFeature] = useState<Feature>("review");
  const [selectedQueue, setSelectedQueue] = useState<QueueKey>("review");
  const [classificationOptions, setClassificationOptions] = useState<ClassificationOption[]>([]);
  const [classificationChoice, setClassificationChoice] = useState("");
  const [classificationReason, setClassificationReason] = useState("");
  const [classificationTask, setClassificationTask] = useState<string | null>(null);
  const [reviewAction, setReviewAction] = useState<ReviewAction | null>(null);
  const [actionReason, setActionReason] = useState("");
  const [queueForms, setQueueForms] = useState<Record<QueueKey, WorkbenchDetail["form"][]>>({
    classification: [], review: [], exceptions: [], exportable: [],
  });

  const selectedField = detail?.fields.find((field) => field.field_id === selectedFieldId) ?? null;
  const reviewEvidence = selectReviewEvidence(detail?.evidence ?? []);
  const hasUnsavedEdits =
    detail !== null &&
    JSON.stringify(edits) !== JSON.stringify(detail.draft?.values ?? {});
  const warningCount = detail?.fields.filter((field) => {
    const best = field.candidates[0];
    const value = fieldValue(detail, field, edits);
    return Boolean(ruleFailures[field.field_name] ?? reviewValueIssue(
      value, best?.confidence,
      Object.hasOwn(edits, field.field_id) || Object.hasOwn(edits, field.field_name),
      field.data_type, field.rules,
    ));
  }).length ?? 0;

  const refreshQueues = useCallback(async () => {
    try {
      const results = await Promise.all(QUEUES.map(async ({ key }) => [key, await api.getQueue(key)] as const));
      setQueueForms(Object.fromEntries(results) as Record<QueueKey, WorkbenchDetail["form"][]>);
    } catch (cause) {
      setError(toMessage(cause));
    }
  }, [api]);

  const loadWorkbenchById = useCallback(async (formId: string) => {
    const cleaned = formId.trim();
    if (!cleaned) {
      setError("请先输入表单编号。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [loadedDetail, loadedHistory] = await Promise.all([
        api.getWorkbench(cleaned),
        api.getHistory(cleaned).catch(() => null),
      ]);
      setFormIdInput(cleaned);
      setDetail(loadedDetail);
      setHistory(loadedHistory);
      setEdits(loadedDetail.draft?.values ?? {});
      setRuleFailures({});
      setSelectedFieldId(loadedDetail.fields[0]?.field_id ?? null);
      setLease(null);
      setClassificationTask(null);
      if (loadedDetail.form.review_status === "NEEDS_CLASSIFICATION") {
        const options = await api.getClassificationOptions(cleaned);
        setClassificationOptions(options);
        setClassificationChoice(
          options[0] ? `${options[0].template_key}@${options[0].version}` : "",
        );
      } else {
        setClassificationOptions([]);
        setClassificationChoice("");
      }
      void refreshQueues();
    } catch (cause) {
      setDetail(null);
      setHistory(null);
      setError(toMessage(cause));
    } finally {
      setLoading(false);
    }
  }, [api, refreshQueues]);

  const loadWorkbench = useCallback(async () => {
    await loadWorkbenchById(formIdInput);
  }, [formIdInput, loadWorkbenchById]);

  useEffect(() => {
    void refreshQueues();
  }, [refreshQueues]);

  useEffect(() => {
    if (!hasUnsavedEdits) return undefined;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [hasUnsavedEdits]);

  function canLeaveCurrentForm(): boolean {
    return !hasUnsavedEdits || window.confirm("当前有尚未保存的审核修改，确定离开吗？");
  }

  function chooseQueue(queueKey: QueueKey) {
    if (!canLeaveCurrentForm()) return;
    setFeature("review");
    setSelectedQueue(queueKey);
  }

  function openQueueForm(formId: string) {
    if (!canLeaveCurrentForm()) return;
    void loadWorkbenchById(formId);
  }

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
    if (hasUnsavedEdits && !window.confirm("尚有未保存修改，释放审核锁后将无法保存，仍要释放吗？")) {
      return;
    }
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
        detail.fields.map((field) => ({
          fieldId: field.field_id,
          currentValue: fieldValue(detail, field, {}),
        })),
        edits,
      );
      const result = await api.confirmAndClaimNext(detail.form.form_id, {
        expectedVersion: detail.form.current_record_version,
        leaseToken: lease.lease_token,
        values,
        reason: "人工审核工作台确认",
        evidenceIds: detail.evidence.map((evidence) => evidence.file_id),
        queueKey: "review",
      });
      await notificationPort.notify({
        title: "表单已确认",
        body: `${detail.form.form_id} 已写入新版本。`,
        level: "success",
        timeoutMs: 3_500,
      });
      if (result.next) {
        setDetail(result.next.workbench);
        setFormIdInput(result.next.workbench.form.form_id);
        setLease(result.next.lease);
        setEdits(result.next.workbench.draft?.values ?? {});
        setRuleFailures({});
        setSelectedFieldId(result.next.workbench.fields[0]?.field_id ?? null);
        setHistory(
          await api.getHistory(result.next.workbench.form.form_id).catch(() => null),
        );
      } else {
        setDetail(null);
        setHistory(null);
        setLease(null);
        setEdits({});
        setRuleFailures({});
        setSelectedFieldId(null);
        setFormIdInput("");
      }
      await refreshQueues();
    } catch (cause) {
      if (cause instanceof ApiRequestError && cause.code === "REVIEW_RULE_BLOCKED") {
        setRuleFailures(Object.fromEntries(
          cause.failures.map((failure) => [failure.field_key, failure.message]),
        ));
        setError("审核规则拦截：请修正电子表格中标红的字段。");
      } else {
        setError(toMessage(cause));
      }
    } finally {
      setLoading(false);
    }
  }

  async function saveDraft() {
    if (!detail || !lease) {
      setError("请先获取审核锁，再保存草稿。");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const values = buildConfirmValues(
        detail.fields.map((field) => ({
          fieldId: field.field_id,
          currentValue: fieldValue(detail, field, {}),
        })),
        edits,
      );
      const draft = await api.saveDraft(detail.form.form_id, {
        expectedVersion: detail.form.current_record_version,
        leaseToken: lease.lease_token,
        values,
      });
      setDetail((current) => current ? { ...current, draft } : current);
      setEdits(draft.values);
      await notificationPort.notify({
        title: "草稿已保存",
        body: `${detail.form.form_id} 的人工修改已保存，正式记录未改变。`,
        level: "success",
        timeoutMs: 3_500,
      });
    } catch (cause) {
      setError(toMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  async function submitReviewAction() {
    if (!detail || !lease || !reviewAction) return;
    if (!actionReason.trim()) {
      setError("退回或作废必须填写原因。");
      return;
    }
    try {
      setLoading(true);
      const input = {
        expectedVersion: detail.form.current_record_version,
        leaseToken: lease.lease_token,
        reason: actionReason.trim(),
        evidenceIds: detail.evidence.map((evidence) => evidence.file_id),
      };
      if (reviewAction === "return") {
        await api.returnForm(detail.form.form_id, input);
      } else {
        await api.voidForm(detail.form.form_id, input);
      }
      await notificationPort.notify({
        title: reviewAction === "return" ? "表单已退回" : "表单已作废",
        body: `${detail.form.form_id} 已完成操作并写入审计。`,
        level: "success",
        timeoutMs: 3_500,
      });
      setReviewAction(null);
      setActionReason("");
      setDetail(null);
      setHistory(null);
      setLease(null);
      setEdits({});
      setRuleFailures({});
      setFormIdInput("");
      await refreshQueues();
    } catch (cause) {
      setError(toMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  async function assignSelectedTemplate() {
    if (!detail || !classificationChoice || !classificationReason.trim()) {
      setError("请选择模板并填写人工分类原因。");
      return;
    }
    const separator = classificationChoice.lastIndexOf("@");
    const templateKey = classificationChoice.slice(0, separator);
    const version = Number(classificationChoice.slice(separator + 1));
    try {
      setLoading(true);
      const result = await api.assignTemplate(detail.form.form_id, {
        templateKey,
        version,
        reason: classificationReason.trim(),
      });
      setClassificationReason("");
      await notificationPort.notify({
        title: "人工分类已保存",
        body: `已创建识别任务 ${result.recognition_task_id}。`,
        level: "success",
        timeoutMs: 4_000,
      });
      await loadWorkbenchById(detail.form.form_id);
      setClassificationTask(result.recognition_task_id);
      await refreshQueues();
    } catch (cause) {
      setError(toMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  async function importImage(file: File | null) {
    if (file === null) return;
    if (!file.type.startsWith("image/")) {
      setError("请选择 PNG、JPEG 或 TIFF 图片。");
      return;
    }
    try {
      setUploading(true);
      setError(null);
      setDuplicateImport(null);
      const response = await fetch("/api/v1/imports", {
        method: "POST",
        headers: {
          "Content-Type": file.type,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: file,
      });
      const payload = (await response.json()) as {
        form_id?: string;
        code?: string;
        detail?: string;
        existing_form?: DuplicateImportInfo["existing_form"];
        actions?: DuplicateImportInfo["actions"];
      };
      if (
        response.status === 409 && payload.code === "DUPLICATE_EVIDENCE" &&
        payload.existing_form && payload.actions
      ) {
        setDuplicateImport({
          code: "DUPLICATE_EVIDENCE",
          detail: payload.detail ?? "该图片已经导入。",
          existing_form: payload.existing_form,
          actions: payload.actions,
        });
        return;
      }
      if (!response.ok || !payload.form_id) {
        throw new Error(payload.detail ?? payload.code ?? "图片导入失败。");
      }
      await loadWorkbenchById(payload.form_id);
    } catch (cause) {
      setError(toMessage(cause));
    } finally {
      setUploading(false);
    }
  }

  async function reopenDuplicateForTest() {
    if (!duplicateImport) return;
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(
        `/api/v1/imports/existing/${encodeURIComponent(duplicateImport.existing_form.form_id)}/reopen-test`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error(await responseDetail(response, "重新启用测试表单失败。"));
      const formId = duplicateImport.existing_form.form_id;
      setDuplicateImport(null);
      await loadWorkbenchById(formId);
    } catch (cause) {
      setError(toMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  async function purgeDuplicateForTest() {
    if (!duplicateImport) return;
    const formId = duplicateImport.existing_form.form_id;
    if (!window.confirm(`彻底清除测试表单 ${formId} 及其全部证据？此操作不可恢复。`)) return;
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`/api/v1/imports/existing/${encodeURIComponent(formId)}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error(await responseDetail(response, "清除测试表单失败。"));
      setDuplicateImport(null);
      if (detail?.form.form_id === formId) {
        setDetail(null);
        setHistory(null);
        setEdits({});
        setFormIdInput("");
      }
      await refreshQueues();
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
    const field = detail?.fields.find((item) => item.field_id === fieldId);
    if (field) clearRuleFailure(field.field_name);
  }

  function editField(fieldId: string, value: string) {
    setEdits((current) => ({ ...current, [fieldId]: value }));
    const field = detail?.fields.find((item) => item.field_id === fieldId);
    if (field) clearRuleFailure(field.field_name);
  }

  function clearRuleFailure(fieldName: string) {
    setRuleFailures((current) => {
      if (!Object.hasOwn(current, fieldName)) return current;
      const next = { ...current };
      delete next[fieldName];
      return next;
    });
  }

  if (feature === "templates") return <TemplateStudio onBack={() => setFeature("review")} />;
  if (feature === "master-data") return <MasterDataNotice onBack={() => setFeature("review")} />;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">▦</span> 产量采集工作台</div>
        <div className="topbar-context">人工审核 <span className="connection-dot" /> 本地服务</div>
      </header>

      <aside className="queue-sidebar" aria-label="工作队列">
        <div className="queue-title">审核队列</div>
        <nav>
          {QUEUES.map((queue) => (
            <QueueItem
              key={queue.key}
              label={queue.label}
              count={String(queueForms[queue.key].length)}
              active={selectedQueue === queue.key}
              warning={queue.warning}
              onClick={() => chooseQueue(queue.key)}
            />
          ))}
        </nav>
        <div className="sidebar-divider" />
        <nav className="secondary-nav">
          <button type="button" onClick={() => {
            if (!canLeaveCurrentForm()) return;
            setFeature("review");
            window.setTimeout(() => document.getElementById("image-import")?.click(), 0);
          }}>数据管理</button>
          <button type="button" onClick={() => {
            if (canLeaveCurrentForm()) setFeature("templates");
          }}>模板与字段</button>
          <button type="button" onClick={() => {
            if (canLeaveCurrentForm()) setFeature("master-data");
          }}>员工 / 工单</button>
          <button type="button" onClick={() => {
            if (canLeaveCurrentForm()) setFeature("master-data");
          }}>产品 / 工序</button>
        </nav>
      </aside>

      <main className="workbench">
        <section className="context-card">
          <form
            className="form-loader"
            onSubmit={(event) => {
              event.preventDefault();
              if (canLeaveCurrentForm()) void loadWorkbench();
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
            <label className="button button-primary import-image-button">
              {uploading ? "正在导入…" : "导入图片"}
              <input
                id="image-import"
                type="file"
                accept="image/png,image/jpeg,image/tiff"
                disabled={uploading}
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  event.target.value = "";
                  void importImage(file);
                }}
              />
            </label>
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
        {duplicateImport && (
          <section className="duplicate-import-card" role="alert">
            <div>
              <strong>图片已经导入</strong>
              <p>{duplicateImport.detail}</p>
              <span>
                表单 {duplicateImport.existing_form.form_id} · {reviewStatusLabel(duplicateImport.existing_form.review_status)}
              </span>
              {duplicateImport.existing_form.review_status === "RECAPTURE_REQUIRED" && (
                <em>该表单已退回，重新采集必须上传内容不同的新照片。</em>
              )}
            </div>
            <div className="duplicate-import-actions">
              {duplicateImport.actions.can_open && <button type="button" className="button button-secondary" onClick={() => {
                const formId = duplicateImport.existing_form.form_id;
                setDuplicateImport(null);
                void loadWorkbenchById(formId);
              }}>打开已有表单</button>}
              {duplicateImport.actions.can_reopen_for_test && <button type="button" className="button button-primary" disabled={loading} onClick={() => void reopenDuplicateForTest()}>重新用于本地测试</button>}
              {duplicateImport.actions.can_purge_for_test && <button type="button" className="button button-danger" disabled={loading} onClick={() => void purgeDuplicateForTest()}>彻底清除测试数据</button>}
            </div>
          </section>
        )}

        <section className="queue-panel" aria-label="当前审核队列">
          <div>
            <span className="eyebrow">当前队列</span>
            <strong>{QUEUES.find((queue) => queue.key === selectedQueue)?.label}</strong>
          </div>
          <div className="queue-form-list">
            {queueForms[selectedQueue].length === 0 ? (
              <span className="muted">当前没有表单</span>
            ) : queueForms[selectedQueue].map((form) => (
              <button key={form.form_id} type="button" onClick={() => openQueueForm(form.form_id)}>
                <strong>{form.form_id}</strong>
                <span>{form.template_id} · {form.review_status} · 优先级 {form.priority}</span>
              </button>
            ))}
          </div>
        </section>

        {detail?.form.review_status === "NEEDS_CLASSIFICATION" ? (
          <section className="classification-card" aria-label="人工模板分类">
            <div>
              <span className="eyebrow">二维码识别失败</span>
              <h2>人工选择已发布模板</h2>
              <p>系统不会猜测模板。选择结果、原因和后续识别任务都会被审计。</p>
            </div>
            <label>
              已发布模板
              <select
                value={classificationChoice}
                onChange={(event) => setClassificationChoice(event.target.value)}
              >
                {classificationOptions.map((option) => (
                  <option
                    key={`${option.template_key}@${option.version}`}
                    value={`${option.template_key}@${option.version}`}
                  >
                    {option.template_key} · V{option.version} · {option.field_count} 字段
                  </option>
                ))}
              </select>
            </label>
            <label>
              分类原因
              <textarea
                value={classificationReason}
                onChange={(event) => setClassificationReason(event.target.value)}
                placeholder="例如：二维码污损，依据纸面标题确认模板"
                maxLength={500}
              />
            </label>
            <button
              type="button"
              className="button button-primary"
              disabled={!classificationChoice || !classificationReason.trim() || loading}
              onClick={() => void assignSelectedTemplate()}
            >
              确认分类并创建识别任务
            </button>
            {classificationTask && (
              <p className="classification-task">识别任务 {classificationTask} 已进入队列。</p>
            )}
          </section>
        ) : (
          <>
            <div className="mobile-pane-switch" role="tablist" aria-label="审核面板">
              <button type="button" className={mobilePane === "evidence" ? "active" : ""} onClick={() => setMobilePane("evidence")}>图片</button>
              <button type="button" className={mobilePane === "fields" ? "active" : ""} onClick={() => setMobilePane("fields")}>电子表格</button>
            </div>

            <section className="review-grid" data-mobile-pane={mobilePane}>
              <EvidenceCanvas
                evidenceUrl={reviewEvidence.evidence?.download_url ?? null}
                coordinateSpace={reviewEvidence.coordinateSpace}
                fields={detail?.fields ?? []}
                selectedFieldId={selectedFieldId}
                imageSize={imageSize}
                onImageLoad={setImageSize}
                onSelectField={selectField}
              />
              <FieldTable
                fields={detail?.fields ?? []}
                edits={edits}
                recordValues={detail?.current_record?.values ?? {}}
                ruleFailures={ruleFailures}
                selectedFieldId={selectedFieldId}
                onSelectField={selectField}
                onEdit={editField}
              />
            </section>

            <section className="detail-drawer">
          <div className="drawer-heading">
            <div>
              <span className="eyebrow">规则与建议</span>
              <strong>{selectedField ? selectedField.display_name ?? selectedField.field_name : "选择一个字段查看详情"}</strong>
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
              )) : <span className="muted">
                {selectedField?.recognition_engine === "manual"
                  ? "该字段配置为人工录入，不会自动生成识别候选"
                  : "暂无 OCR/OMR 候选"}
              </span>}
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
              <button
                type="button"
                className="button button-danger-secondary"
                disabled={!detail || !lease || loading}
                onClick={() => setReviewAction("return")}
              >退回</button>
              <button
                type="button"
                className="button button-danger-secondary"
                disabled={!detail || !lease || loading}
                onClick={() => setReviewAction("void")}
              >作废</button>
              <button
                type="button"
                className="button button-secondary"
                disabled={!detail || !lease || loading || !hasUnsavedEdits}
                onClick={() => void saveDraft()}
              >保存草稿</button>
              <span className="action-hint">
                {detail?.draft
                  ? `草稿由 ${detail.draft.saved_by} 保存于 ${new Date(detail.draft.updated_at).toLocaleTimeString()}`
                  : "确认会创建新版本并原子领取下一张"}
              </span>
              <button
                type="button"
                className="button button-primary"
                disabled={!detail || !lease || loading || selectedQueue !== "review" || warningCount > 0}
                title={warningCount > 0 ? "请先处理所有待确认字段" : undefined}
                onClick={() => void confirmAndNext()}
              >
                确认并下一张
              </button>
            </footer>
          </>
        )}
      </main>
      {reviewAction && (
        <ReviewActionDialog
          action={reviewAction}
          reason={actionReason}
          loading={loading}
          onReasonChange={setActionReason}
          onCancel={() => {
            setReviewAction(null);
            setActionReason("");
          }}
          onConfirm={() => void submitReviewAction()}
        />
      )}
    </div>
  );
}

function QueueItem({ label, count, active = false, warning = false, onClick }: { label: string; count: string; active?: boolean; warning?: boolean; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={`queue-item ${active ? "active" : ""} ${warning ? "warning" : ""}`}><span>{label}</span><span>{count}</span></button>;
}

function ReviewActionDialog({
  action,
  reason,
  loading,
  onReasonChange,
  onCancel,
  onConfirm,
}: {
  action: ReviewAction;
  reason: string;
  loading: boolean;
  onReasonChange: (reason: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const isVoid = action === "void";
  return (
    <div className="dialog-backdrop" role="presentation">
      <section
        className="review-action-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-action-title"
      >
        <span className="eyebrow">需写入审计原因</span>
        <h2 id="review-action-title">{isVoid ? "作废当前表单" : "退回当前表单"}</h2>
        <p>
          {isVoid
            ? "作废会创建不可变的 VOIDED 记录版本，并从审核队列移除。"
            : "退回会清除审核草稿和租约，并将表单送入重新采集队列。"}
        </p>
        <label>
          操作原因
          <textarea
            autoFocus
            value={reason}
            maxLength={500}
            onChange={(event) => onReasonChange(event.target.value)}
          />
        </label>
        <div className="dialog-actions">
          <button type="button" className="button button-secondary" onClick={onCancel}>
            取消
          </button>
          <button
            type="button"
            className="button button-danger"
            disabled={!reason.trim() || loading}
            onClick={onConfirm}
          >
            确认{isVoid ? "作废" : "退回"}
          </button>
        </div>
      </section>
    </div>
  );
}

function MasterDataNotice({ onBack }: { onBack: () => void }) {
  return (
    <main className="master-data-notice">
      <button type="button" className="text-button" onClick={onBack}>← 返回审核工作台</button>
      <section>
        <span className="eyebrow">主数据中心</span>
        <h1>员工、工单、产品与工序</h1>
        <p>当前代码只提供主数据规则校验，没有持久化表和编辑 API。这里不再显示无法保存的伪表单。</p>
        <p>下一步会先补主数据的 SQLite 迁移、权限接口与编辑页面，再把模板字段的下拉选项接入这些数据。</p>
      </section>
    </main>
  );
}

function EvidenceCanvas({
  evidenceUrl,
  coordinateSpace,
  fields,
  selectedFieldId,
  imageSize,
  onImageLoad,
  onSelectField,
}: {
  evidenceUrl: string | null;
  coordinateSpace: "canonical" | "original" | "none";
  fields: ReviewField[];
  selectedFieldId: string | null;
  imageSize: { width: number; height: number };
  onImageLoad: (size: { width: number; height: number }) => void;
  onSelectField: (field: ReviewField) => void;
}) {
  const alignmentReady = coordinateSpace === "canonical";
  return (
    <section className="evidence-panel" aria-label="表单图像证据">
      <div className="panel-toolbar">
        <strong>{alignmentReady ? "校正后的表单" : "原始表单证据"}</strong>
        <span>{alignmentReady ? "四角定位已应用 · 标准坐标" : "未完成四角校正"}</span>
      </div>
      {coordinateSpace === "original" && (
        <div className="alignment-warning" role="status">
          未生成校正图，已隐藏标准字段框，避免将模板坐标错误覆盖到原图。
        </div>
      )}
      <div className="canvas-stage">
        {evidenceUrl ? (
          <div className="image-wrap">
            <img src={evidenceUrl} alt="原始表单" onLoad={(event) => onImageLoad({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} />
            {alignmentReady && fields.map((field) => {
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
  recordValues,
  ruleFailures,
  selectedFieldId,
  onSelectField,
  onEdit,
}: {
  fields: ReviewField[];
  edits: Record<string, unknown>;
  recordValues: Record<string, unknown>;
  ruleFailures: Record<string, string>;
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
          const displayValue = valueForField(field, edits, recordValues);
          const issue = ruleFailures[field.field_name] ?? reviewValueIssue(
            displayValue, candidate?.confidence,
            Object.hasOwn(edits, field.field_id) || Object.hasOwn(edits, field.field_name),
            field.data_type, field.rules,
          );
          const hasWarning = issue !== null;
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
              <span className="field-name"><strong>{field.display_name ?? field.field_name}</strong>{field.display_name && <small>{field.field_name}</small>}</span>
              <span className="candidate-value">
                {candidate ? stringValue(candidate.candidate_value) : field.recognition_engine === "manual" ? "人工录入" : "—"}
              </span>
              <span>{candidate ? `${Math.round(candidate.confidence * 100)}%` : "—"}</span>
              <span onClick={(event) => event.stopPropagation()}>{field.rules?.allowed_values.length ? <select aria-label={`${field.display_name ?? field.field_name} 确认值`} value={stringValue(displayValue)} onChange={(event) => onEdit(field.field_id, event.target.value)}><option value="">请选择</option>{field.rules.allowed_values.map((value) => <option key={value} value={value}>{value}</option>)}</select> : <input aria-label={`${field.display_name ?? field.field_name} 确认值`} value={stringValue(displayValue)} onChange={(event) => onEdit(field.field_id, event.target.value)} />}</span>
              <span>{hasWarning ? <><em className="inline-warning">待确认</em><small className="field-rule-message">{issue}</small></> : <em className="inline-success">已就绪</em>}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function fieldValue(
  detail: WorkbenchDetail | null,
  field: ReviewField,
  edits: Readonly<Record<string, unknown>>,
): unknown {
  return valueForField(field, edits, detail?.current_record?.values ?? {});
}

function valueForField(
  field: ReviewField,
  edits: Readonly<Record<string, unknown>>,
  recordValues: Readonly<Record<string, unknown>>,
): unknown {
  if (Object.hasOwn(edits, field.field_id)) return edits[field.field_id];
  if (Object.hasOwn(edits, field.field_name)) return edits[field.field_name];
  if (Object.hasOwn(recordValues, field.field_id)) return recordValues[field.field_id];
  if (Object.hasOwn(recordValues, field.field_name)) return recordValues[field.field_name];
  return field.current_value;
}

function toMessage(cause: unknown): string {
  if (cause instanceof ApiRequestError) return `${cause.code}：${cause.message}`;
  return cause instanceof Error ? cause.message : "请求无法完成。";
}

async function responseDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as {
      code?: string;
      detail?: string | { code?: string };
    };
    if (typeof payload.detail === "string") return payload.detail;
    return payload.detail?.code ?? payload.code ?? fallback;
  } catch {
    return fallback;
  }
}

function reviewStatusLabel(status: string): string {
  return ({
    NEEDS_CLASSIFICATION: "待人工分类",
    CLASSIFIED: "待复核",
    RECAPTURE_REQUIRED: "已退回，需重新采集",
    VOIDED: "已作废",
    CONFIRMED: "已确认",
  } as Record<string, string>)[status] ?? status;
}
