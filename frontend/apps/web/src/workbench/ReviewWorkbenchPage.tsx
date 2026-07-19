import {
  ApiRequestError,
  ReviewWorkbenchApi,
  TaskApi,
  type ClassificationOption,
  type RecognitionCandidate,
  type ReviewField,
  type ReviewHistory,
  type ReviewLease,
  type WorkbenchDetail,
} from "@form-detection/api-client";
import { WebNotificationPort } from "@form-detection/shell-ports";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  buildConfirmValues,
  reviewValueIssue,
} from "../review-model";
import { businessErrorMessage, businessProblemMessage } from "../ui/business-errors";
import { getReviewStatusCopy } from "../ui/business-language";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { EvidenceViewer } from "./EvidenceViewer";
import { ClassificationStage } from "./ClassificationStage";
import { RecaptureStage } from "./RecaptureStage";
import { FieldDetailPanel } from "./FieldDetailPanel";
import { FieldReviewTable } from "./FieldReviewTable";
import { fieldUsesAutomaticRecognition, workerNumberIssue } from "./field-behavior";
import { selectFirstIssueFieldId } from "./field-navigation";
import { WorkbenchActionBar } from "./WorkbenchActionBar";
import { WorkbenchEmptyState, WorkbenchErrorNotice } from "./WorkbenchEmptyState";
import { WorkbenchHeader } from "./WorkbenchHeader";
import { WorkbenchQueue } from "./WorkbenchQueue";
import { useWorkbenchShortcuts, type ImageShortcutCommand } from "./useWorkbenchShortcuts";
import type {
  DuplicateImportInfo,
  MobilePane,
  QueueKey,
  ReviewAction,
} from "./workbench-types";

const notificationPort = new WebNotificationPort();

const QUEUES: Array<{ key: QueueKey; label: string; warning?: boolean }> = [
  { key: "classification", label: "待确认表单类型" },
  { key: "review", label: "待核对" },
  { key: "exceptions", label: "待重新拍照", warning: true },
];

interface ReviewWorkbenchPageProps {
  routeQueue?: QueueKey;
  routeFormId?: string;
  onQueueRouteChange?: (queue: QueueKey) => void;
}
export function ReviewWorkbenchPage({
  routeQueue,
  routeFormId,
  onQueueRouteChange,
}: ReviewWorkbenchPageProps) {
  const api = useMemo(() => new ReviewWorkbenchApi("/api/v1"), []);
  const taskApi = useMemo(() => new TaskApi("/api/v1"), []);
  const [formIdInput, setFormIdInput] = useState("");
  const [detail, setDetail] = useState<WorkbenchDetail | null>(null);
  const [history, setHistory] = useState<ReviewHistory | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, unknown>>({});
  const [ruleFailures, setRuleFailures] = useState<Record<string, string>>({});
  const [lease, setLease] = useState<ReviewLease | null>(null);
  const [hoveredFieldId, setHoveredFieldId] = useState<string | null>(null);
  const [splitPercent, setSplitPercent] = useState(() => {
    const stored = Number(globalThis.localStorage?.getItem("review-workbench-split-percent"));
    return Number.isFinite(stored) && stored >= 35 && stored <= 65 ? stored : 46;
  });
  const gridRef = useRef<HTMLElement | null>(null);
  const splitDragging = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [duplicateImport, setDuplicateImport] = useState<DuplicateImportInfo | null>(null);
  const [mobilePane, setMobilePane] = useState<MobilePane>("evidence");
  const [selectedQueue, setSelectedQueue] = useState<QueueKey>(routeQueue ?? "review");
  const [classificationOptions, setClassificationOptions] = useState<ClassificationOption[]>([]);
  const [reviewAction, setReviewAction] = useState<ReviewAction | null>(null);
  const [actionReason, setActionReason] = useState("");
  const [queueForms, setQueueForms] = useState<Record<QueueKey, WorkbenchDetail["form"][]>>({
    classification: [], review: [], exceptions: [],
  });
  const routedFormLoad = useRef<string | null>(null);

  const selectedField = detail?.fields.find((field) => field.field_id === selectedFieldId) ?? null;
  const hasUnsavedEdits =
    detail !== null &&
    JSON.stringify(edits) !== JSON.stringify(detail.draft?.values ?? {});
  const issueFieldIds = detail?.fields.filter((field) => {
    const best = fieldUsesAutomaticRecognition(field) ? field.candidates[0] : undefined;
    const value = fieldValue(detail, field, edits);
    return Boolean(ruleFailures[field.field_name] ?? workerNumberIssue(field, value) ?? reviewValueIssue(
      value, best?.confidence,
      Object.hasOwn(edits, field.field_id) || Object.hasOwn(edits, field.field_name) ||
        field.current_value_source === "HUMAN_CONFIRMED",
      field.data_type, field.rules,
      field.requires_manual_confirmation,
    ));
  }).map((field) => field.field_id) ?? [];
  const warningCount = issueFieldIds.length;
  const isCorrection = (detail?.form.current_record_version ?? 0) > 0;

  useWorkbenchShortcuts({
    fieldIds: detail?.fields.map((field) => field.field_id) ?? [],
    issueFieldIds,
    selectedFieldId,
    hasLease: Boolean(lease),
    hasUnsavedEdits,
    onAcceptCandidate: () => {
      const candidate = selectedField?.candidates[0];
      if (selectedField && candidate) useCandidate(selectedField.field_id, candidate);
    },
    onSelectField: (fieldId) => selectField(fieldId, true),
    onSaveDraft: () => void saveDraft(),
    onImageCommand: runImageShortcut,
  });

  function runImageShortcut(command: ImageShortcutCommand) {
    const labels: Record<ImageShortcutCommand, string[]> = {
      "zoom-in": ["放大"],
      "zoom-out": ["缩小"],
      reset: ["重置"],
      rotate: ["旋转", "顺时针"],
    };
    const root = document.querySelector("[data-workbench-image-context]");
    const button = Array.from(root?.querySelectorAll("button") ?? []).find((candidate) =>
      labels[command].some((label) => candidate.textContent?.includes(label) || candidate.getAttribute("aria-label")?.includes(label)),
    );
    button?.click();
  }

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
      setSelectedFieldId(selectFirstIssueFieldId(
        loadedDetail.fields,
        loadedDetail.draft?.values ?? {},
        {},
      ));
      setHoveredFieldId(null);
      setLease(null);
      if (loadedDetail.form.review_status === "NEEDS_CLASSIFICATION") {
        const options = await api.getClassificationOptions(cleaned);
        setClassificationOptions(options);
      } else {
        setClassificationOptions([]);
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
    if (routeQueue) setSelectedQueue(routeQueue);
  }, [routeQueue]);

  useEffect(() => {
    if (!routeFormId || routedFormLoad.current === routeFormId) return;
    routedFormLoad.current = routeFormId;
    void loadWorkbenchById(routeFormId);
  }, [loadWorkbenchById, routeFormId]);

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
    setSelectedQueue(queueKey);
    onQueueRouteChange?.(queueKey);
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
        setError(`本次审核已结束：${toMessage(cause)}`);
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
    if (hasUnsavedEdits && !window.confirm("尚有未保存修改，暂停审核后将无法保存，仍要暂停吗？")) {
      return;
    }
    try {
      await api.releaseLease(detail.form.form_id, lease.lease_token);
      setLease(null);
    } catch (cause) {
      setError(toMessage(cause));
    }
  }

  async function submitPrimaryReviewAction() {
    if (!detail) return;
    if (!lease) {
      setError("请先开始审核，再确认表单。");
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
      const manuallyConfirmedFieldKeys = manualConfirmationKeys(detail, edits);
      if (detail.form.current_record_version > 0) {
        const formId = detail.form.form_id;
        await api.confirm(formId, {
          expectedVersion: detail.form.current_record_version,
          leaseToken: lease.lease_token,
          values,
          reason: "人工审核工作台更正",
          evidenceIds: detail.evidence.map((evidence) => evidence.file_id),
          manuallyConfirmedFieldKeys,
        });
        const [updatedDetail, updatedHistory] = await Promise.all([
          api.getWorkbench(formId),
          api.getHistory(formId).catch(() => null),
        ]);
        setDetail(updatedDetail);
        setHistory(updatedHistory);
        setFormIdInput(formId);
        setEdits(updatedDetail.draft?.values ?? {});
        setRuleFailures({});
        setSelectedFieldId(selectFirstIssueFieldId(
          updatedDetail.fields,
          updatedDetail.draft?.values ?? {},
          {},
        ));
        setClassificationOptions([]);
        await refreshQueues();
        await notificationPort.notify({
          title: "表单更正已保存",
          body: `${formId} 已写入第 ${updatedDetail.form.current_record_version} 版。`,
          level: "success",
          timeoutMs: 3_500,
        });
        return;
      }
      const result = await api.confirmAndClaimNext(detail.form.form_id, {
        expectedVersion: detail.form.current_record_version,
        leaseToken: lease.lease_token,
        values,
        reason: "人工审核工作台确认",
        evidenceIds: detail.evidence.map((evidence) => evidence.file_id),
        queueKey: "review",
        manuallyConfirmedFieldKeys,
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
        setSelectedFieldId(selectFirstIssueFieldId(
          result.next.workbench.fields,
          result.next.workbench.draft?.values ?? {},
          {},
        ));
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
      setError("请先开始审核，再保存草稿。");
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

  function selectField(fieldId: string, focusFinalValue = false) {
    setSelectedFieldId(fieldId);
    setMobilePane("fields");
    if (!focusFinalValue) return;
    window.requestAnimationFrame(() => {
      const row = document.getElementById(`review-field-row-${fieldId}`);
      const input = document.getElementById(`review-final-${fieldId}`) as HTMLElement | null;
      row?.scrollIntoView({ block: "center" });
      input?.focus();
    });
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

  return (
    <div className="review-workbench-shell">
      <main className="workbench">
        <nav className="workbench-queue-tabs" aria-label="审核任务" role="tablist">
          {QUEUES.map((queue) => (
            <QueueTab
              key={queue.key}
              label={queue.label}
              count={String(queueForms[queue.key].length)}
              active={selectedQueue === queue.key}
              warning={queue.warning}
              onClick={() => chooseQueue(queue.key)}
            />
          ))}
        </nav>
        <WorkbenchHeader
          formIdInput={formIdInput}
          detail={detail}
          lease={lease}
          loading={loading}
          uploading={uploading}
          onFormIdInputChange={setFormIdInput}
          onLoad={() => {
            if (canLeaveCurrentForm()) void loadWorkbench();
          }}
          onImportImage={(file) => void importImage(file)}
          onAcquireLease={() => void acquireLease()}
          onReleaseLease={() => void releaseLease()}
        />

        {error && <WorkbenchErrorNotice error={error} />}
        {duplicateImport && (
          <section className="duplicate-import-card" role="alert">
            <div>
              <strong>图片已经导入</strong>
              <p>{duplicateImport.detail}</p>
              <span>
                表单 {duplicateImport.existing_form.form_id} · {getReviewStatusCopy(duplicateImport.existing_form.review_status).label}
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

        <WorkbenchQueue
          selectedQueue={selectedQueue}
          forms={queueForms[selectedQueue]}
          onOpenForm={openQueueForm}
        />

        {!detail ? (
          <WorkbenchEmptyState
            queue={selectedQueue}
            onUpload={() => document.getElementById("image-import")?.click()}
            onFind={() => document.querySelector<HTMLInputElement>('[aria-label="表单编号"]')?.focus()}
          />
        ) : detail.form.review_status === "NEEDS_CLASSIFICATION" ? (
          <ClassificationStage
            key={detail.form.form_id}
            formId={detail.form.form_id}
            detail={detail}
            options={classificationOptions}
            assignTemplate={async (input) => {
              const result = await api.assignTemplate(detail.form.form_id, input);
              await notificationPort.notify({
                title: "人工分类已保存",
                body: `已创建识别任务 ${result.recognition_task_id}。`,
                level: "success",
                timeoutMs: 4_000,
              });
              return result;
            }}
            taskApi={taskApi}
            onRecognitionSucceeded={async () => {
              await loadWorkbenchById(detail.form.form_id);
              await refreshQueues();
            }}
            onError={setError}
          />
        ) : detail.form.review_status === "RECAPTURE_REQUIRED" ? (
          <RecaptureStage
            detail={detail}
            history={history}
            onUpload={(file) => void importImage(file)}
          />
        ) : (
          <>
            <div className="mobile-pane-switch" role="tablist" aria-label="审核面板">
              <button type="button" role="tab" aria-selected={mobilePane === "evidence"} className={mobilePane === "evidence" ? "active" : ""} onClick={() => setMobilePane("evidence")}>图片</button>
              <button type="button" role="tab" aria-selected={mobilePane === "fields"} className={mobilePane === "fields" ? "active" : ""} onClick={() => setMobilePane("fields")}>电子表格</button>
            </div>

            <section
              ref={gridRef}
              className="review-grid"
              data-testid="review-workbench-grid"
              data-mobile-pane={mobilePane}
              style={{ gridTemplateColumns: `${splitPercent}% ${100 - splitPercent}%` }}
            >
              <div className="evidence-shortcut-context" data-workbench-image-context>
                <EvidenceViewer
                  evidence={detail.evidence}
                  fields={detail.fields}
                  selectedFieldId={selectedFieldId}
                  hoveredFieldId={hoveredFieldId}
                  onSelectField={(fieldId) => selectField(fieldId, true)}
                  onHoverField={setHoveredFieldId}
                />
              </div>
              <div
                className="workbench-splitter"
                role="separator"
                aria-label="调整图片与电子表格宽度"
                aria-orientation="vertical"
                aria-valuemin={35}
                aria-valuemax={65}
                aria-valuenow={splitPercent}
                style={{ left: `${splitPercent}%` }}
                onPointerDown={() => { splitDragging.current = true; }}
                onPointerMove={(event) => {
                  if (!splitDragging.current || !gridRef.current) return;
                  const bounds = gridRef.current.getBoundingClientRect();
                  const next = Math.min(65, Math.max(35, Math.round(((event.clientX - bounds.left) / bounds.width) * 100)));
                  setSplitPercent(next);
                  globalThis.localStorage?.setItem("review-workbench-split-percent", String(next));
                }}
                onPointerUp={() => { splitDragging.current = false; }}
                onPointerCancel={() => { splitDragging.current = false; }}
              />
              <FieldReviewTable
                fields={detail?.fields ?? []}
                edits={edits}
                recordValues={detail?.current_record?.values ?? {}}
                ruleFailures={ruleFailures}
                selectedFieldId={selectedFieldId}
                hoveredFieldId={hoveredFieldId}
                onSelectField={(fieldId) => selectField(fieldId)}
                onHoverField={setHoveredFieldId}
                onEdit={editField}
              />
            </section>

            <FieldDetailPanel
              selectedField={selectedField}
              evidence={detail?.evidence ?? []}
              history={history}
              warningCount={warningCount}
              ruleFailure={selectedField ? ruleFailures[selectedField.field_id] ?? ruleFailures[selectedField.field_name] ?? null : null}
              onUseCandidate={useCandidate}
            />

            <WorkbenchActionBar
              detail={detail}
              lease={lease}
              loading={loading}
              hasUnsavedEdits={hasUnsavedEdits}
              warningCount={warningCount}
              isCorrection={isCorrection}
              selectedQueue={selectedQueue}
              onReturn={() => setReviewAction("return")}
              onVoid={() => setReviewAction("void")}
              onSaveDraft={() => void saveDraft()}
              onPrimary={() => void submitPrimaryReviewAction()}
            />
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

function QueueTab({ label, count, active = false, warning = false, onClick }: { label: string; count: string; active?: boolean; warning?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`workbench-queue-tab ${active ? "active" : ""} ${warning ? "warning" : ""}`}
    >
      <span>{label}</span><strong>{count}</strong>
    </button>
  );
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
    <ConfirmDialog
      title={isVoid ? "作废当前表单" : "退回当前表单"}
      description={isVoid
        ? "作废会保存不可更改的操作记录，并将表单从审核队列移除。"
        : "退回会清除审核草稿、结束本次审核，并将表单送入重新采集队列。"}
      confirmLabel={isVoid ? "确认作废当前表单" : "确认退回当前表单"}
      cancelLabel={isVoid ? "取消作废" : "取消退回"}
      loading={loading}
      confirmDisabled={!reason.trim()}
      onCancel={onCancel}
      onConfirm={onConfirm}
    >
        <label>
          操作原因
          <textarea
            value={reason}
            maxLength={500}
            onChange={(event) => onReasonChange(event.target.value)}
          />
        </label>
    </ConfirmDialog>
  );
}

function fieldValue(
  detail: WorkbenchDetail | null,
  field: ReviewField,
  edits: Readonly<Record<string, unknown>>,
): unknown {
  return valueForField(field, edits, detail?.current_record?.values ?? {});
}

function manualConfirmationKeys(
  detail: WorkbenchDetail,
  edits: Readonly<Record<string, unknown>>,
): string[] {
  return detail.fields.filter((field) => (
    field.requires_manual_confirmation && (
      Object.hasOwn(edits, field.field_id) ||
      Object.hasOwn(edits, field.field_name) ||
      field.current_value_source === "HUMAN_CONFIRMED"
    )
  )).map((field) => field.field_name);
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
  return businessErrorMessage(cause, "审核请求无法完成。");
}

async function responseDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as {
      code?: string;
      detail?: string | { code?: string };
    };
    return businessProblemMessage(payload, fallback);
  } catch {
    return fallback;
  }
}
