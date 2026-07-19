import {
  ExportApi,
  type CreateExportInput,
  type CreateExportResponse,
  type ExportBatch,
  type ExportExclusionReason,
  type ExportFilters,
  type ExportPreview,
  type ReportDefinition,
  type ReportAssistantInput,
  type ReportAssistantResult,
  type ExportTask,
  type WaitForExportTaskOptions,
} from "@form-detection/api-client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ProblemNotice } from "./ui/ProblemNotice";
import { TraceDetails } from "./ui/TraceDetails";
import { businessErrorMessage } from "./ui/business-errors";
import { getTaskStatusCopy } from "./ui/business-language";

export interface ExportCenterApi {
  preview(filters: ExportFilters, signal?: AbortSignal): Promise<ExportPreview>;
  create(input: CreateExportInput, idempotencyKey: string): Promise<CreateExportResponse>;
  waitForTask(taskId: string, options?: WaitForExportTaskOptions): Promise<ExportTask>;
  listBatches(): Promise<ExportBatch[]>;
  getBatch(batchId: string): Promise<ExportBatch>;
  downloadBatch(batchId: string): Promise<Blob>;
  listReportDefinitions(): Promise<ReportDefinition[]>;
  askReportAssistant(input: ReportAssistantInput): Promise<ReportAssistantResult>;
}

interface ExportCenterProps {
  api?: ExportCenterApi;
}

interface PreviewSnapshot {
  result: ExportPreview;
  filters: ExportFilters;
  generation: number;
}

const EMPTY_FILTERS: ExportFilters = {
  form_id: "",
  employee_id: "",
  work_order_id: "",
  review_status: undefined,
  export_status: "NOT_EXPORTED",
};

export function ExportCenter({ api }: ExportCenterProps) {
  const client = useMemo<ExportCenterApi>(() => api ?? new ExportApi("/api/v1"), [api]);
  const [filters, setFilters] = useState<ExportFilters>(EMPTY_FILTERS);
  const [activeTab, setActiveTab] = useState<"quick" | "custom" | "history">("quick");
  const [reportDefinitions, setReportDefinitions] = useState<ReportDefinition[]>([]);
  const [selectedDefinitionId, setSelectedDefinitionId] = useState("");
  const [quickPreview, setQuickPreview] = useState<ExportPreview | null>(null);
  const [previewSnapshot, setPreviewSnapshot] = useState<PreviewSnapshot | null>(null);
  const [batches, setBatches] = useState<ExportBatch[]>([]);
  const [batchDetail, setBatchDetail] = useState<ExportBatch | null>(null);
  const [task, setTask] = useState<ExportTask | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [quickPreviewing, setQuickPreviewing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [needsRecheck, setNeedsRecheck] = useState(false);
  const [lastSupersedesBatchId, setLastSupersedesBatchId] = useState<string | undefined>();
  const [busyBatchId, setBusyBatchId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [assistantQuestion, setAssistantQuestion] = useState("");
  const [assistantResult, setAssistantResult] = useState<ReportAssistantResult | null>(null);
  const [assistantBusy, setAssistantBusy] = useState(false);
  const mounted = useRef(true);
  const pollingController = useRef<AbortController | null>(null);
  const quickPreviewController = useRef<AbortController | null>(null);
  const previewController = useRef<AbortController | null>(null);
  const previewGeneration = useRef(0);
  const batchGeneration = useRef(0);
  const preview = previewSnapshot?.result ?? null;
  const selectedDefinition = reportDefinitions.find(
    (definition) => definition.definition_id === selectedDefinitionId,
  );
  const quickDefinition = reportDefinitions.find(
    (definition) => definition.report_key === "PAYROLL_DETAIL",
  );

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      pollingController.current?.abort();
      quickPreviewController.current?.abort();
      previewController.current?.abort();
    };
  }, []);

  const refreshBatches = useCallback(async () => {
    const generation = ++batchGeneration.current;
    try {
      const loaded = await client.listBatches();
      if (mounted.current && generation === batchGeneration.current) setBatches(loaded);
    } catch (cause) {
      if (mounted.current && generation === batchGeneration.current) setError(toMessage(cause));
    }
  }, [client]);

  useEffect(() => {
    void refreshBatches();
  }, [refreshBatches]);

  useEffect(() => {
    let active = true;
    void client.listReportDefinitions().then((definitions) => {
      if (!active) return;
      const published = definitions.filter((definition) => definition.status === "PUBLISHED");
      setReportDefinitions(published);
      setSelectedDefinitionId((current) => (
        published.some((definition) => definition.definition_id === current)
          ? current
          : published.find((definition) => definition.report_key === "PAYROLL_DETAIL")
            ?.definition_id ?? published[0]?.definition_id ?? ""
      ));
    }).catch((cause: unknown) => {
      if (active) setError(toMessage(cause));
    });
    return () => { active = false; };
  }, [client]);

  const loadQuickPreview = useCallback(async () => {
    quickPreviewController.current?.abort();
    const controller = new AbortController();
    quickPreviewController.current = controller;
    setQuickPreviewing(true);
    setError(null);
    try {
      const result = await client.preview(normalizeFilters(EMPTY_FILTERS), controller.signal);
      if (mounted.current && !controller.signal.aborted) setQuickPreview(result);
    } catch (cause) {
      if (!isAbortError(cause) && mounted.current) setError(toMessage(cause));
    } finally {
      if (quickPreviewController.current === controller) quickPreviewController.current = null;
      if (mounted.current && !controller.signal.aborted) setQuickPreviewing(false);
    }
  }, [client]);

  const askAssistant = useCallback(async () => {
    const question = assistantQuestion.trim();
    if (!question) return;
    setAssistantBusy(true);
    try {
      const activePreview = activeTab === "quick" ? quickPreview : preview;
      const reasonCodes = Array.from(new Set(
        activePreview?.excluded.flatMap((item) => (
          item.reasons?.map((reason) => reason.code) ?? (item.reason ? [item.reason] : [])
        )) ?? [],
      ));
      const result = await client.askReportAssistant({
        question,
        ...(selectedDefinitionId ? { selected_report_definition_id: selectedDefinitionId } : {}),
        ...(activePreview ? {
          preview_summary: {
            included_count: activePreview.included.length,
            excluded_count: activePreview.excluded.length,
            reason_codes: reasonCodes,
          },
        } : {}),
      });
      if (mounted.current) setAssistantResult(result);
    } catch {
      if (mounted.current) setAssistantResult({
        status: "UNAVAILABLE",
        answer: "AI 助手暂时不可用，不影响人工检查和导出。",
        suggested_report_definition_id: null,
        suggested_filter_fields: [],
        next_steps: ["继续使用当前报表和检查结果"],
        requires_user_confirmation: true,
      });
    } finally {
      if (mounted.current) setAssistantBusy(false);
    }
  }, [activeTab, assistantQuestion, client, preview, quickPreview, selectedDefinitionId]);

  useEffect(() => {
    void loadQuickPreview();
  }, [loadQuickPreview]);

  function changeFilter<K extends keyof ExportFilters>(key: K, value: ExportFilters[K]) {
    const nextValue = key === "export_status"
      ? value === "REEXPORT_REQUIRED" ? value : "NOT_EXPORTED"
      : value || undefined;
    const checkInProgress = previewController.current !== null;
    previewController.current?.abort();
    previewController.current = null;
    previewGeneration.current += 1;
    setFilters((current) => ({ ...current, [key]: nextValue }));
    setNeedsRecheck(
      (currentNeedsRecheck) =>
        currentNeedsRecheck || previewSnapshot !== null || checkInProgress,
    );
    setPreviewSnapshot(null);
    setTask(null);
    setPreviewing(false);
    setMessage(null);
  }

  function changeExportType(value: string) {
    const checkInProgress = previewController.current !== null;
    previewController.current?.abort();
    previewController.current = null;
    previewGeneration.current += 1;
    setSelectedDefinitionId(value);
    setNeedsRecheck(
      (currentNeedsRecheck) =>
        currentNeedsRecheck || previewSnapshot !== null || checkInProgress,
    );
    setPreviewSnapshot(null);
    setTask(null);
    setPreviewing(false);
    setMessage(null);
  }

  async function loadPreview() {
    previewController.current?.abort();
    const controller = new AbortController();
    previewController.current = controller;
    const generation = ++previewGeneration.current;
    const filterSnapshot = normalizeFilters(filters);
    setPreviewing(true);
    setError(null);
    setMessage(null);
    try {
      const result = await client.preview(filterSnapshot, controller.signal);
      if (
        mounted.current &&
        !controller.signal.aborted &&
        generation === previewGeneration.current
      ) {
        setPreviewSnapshot({ result, filters: filterSnapshot, generation });
        setNeedsRecheck(false);
      }
    } catch (cause) {
      if (!isAbortError(cause) && mounted.current && generation === previewGeneration.current) {
        setError(toMessage(cause));
      }
    } finally {
      if (previewController.current === controller) previewController.current = null;
      if (mounted.current && generation === previewGeneration.current) setPreviewing(false);
    }
  }

  async function createExport(
    supersedesBatchId?: string,
    activePreview: PreviewSnapshot | null = previewSnapshot,
    requestedExportType = selectedDefinition?.report_key ?? "",
    requireCurrentGeneration = true,
    reportDefinitionId = selectedDefinition?.definition_id,
  ) {
    if (
      !activePreview?.result.included.length ||
      (requireCurrentGeneration && activePreview.generation !== previewGeneration.current) ||
      !requestedExportType.trim()
    ) return;
    if (activePreview.filters.export_status === "REEXPORT_REQUIRED" && !supersedesBatchId) return;
    setLastSupersedesBatchId(supersedesBatchId);
    setCreating(true);
    setError(null);
    setMessage(null);
    setTask(null);
    pollingController.current?.abort();
    const controller = new AbortController();
    pollingController.current = controller;
    let createdTaskId: string | null = null;
    try {
      const created = await client.create({
        export_type: requestedExportType.trim(),
        filters: activePreview.filters,
        ...(reportDefinitionId ? { report_definition_id: reportDefinitionId } : {}),
        ...(supersedesBatchId ? { supersedes_batch_id: supersedesBatchId } : {}),
      }, makeIdempotencyKey());
      createdTaskId = created.task_id;
      if (!mounted.current || controller.signal.aborted) return;
      setTask({
        task_id: created.task_id,
        operation: "XLSX_EXPORT",
        resource_id: "EXPORTS",
        status: created.status,
        progress: 0,
        step: "PENDING",
        error: null,
      });
      const completed = await client.waitForTask(created.task_id, {
        signal: controller.signal,
        onUpdate: (update) => {
          if (mounted.current && !controller.signal.aborted) setTask(update);
        },
      });
      if (!mounted.current || controller.signal.aborted) return;
      setTask(completed);
      if (completed.status === "SUCCEEDED") {
        setMessage("Excel 已生成，可在本步骤或下方导出记录中下载。");
        await refreshBatches();
      }
    } catch (cause) {
      if (!isAbortError(cause) && mounted.current) {
        const failureMessage = toMessage(cause);
        if (createdTaskId) {
          setTask({
            task_id: createdTaskId,
            operation: "XLSX_EXPORT",
            resource_id: "EXPORTS",
            status: "FAILED",
            progress: 0,
            step: "PENDING",
            error: failureMessage,
          });
        } else {
          setError(failureMessage);
        }
      }
    } finally {
      if (pollingController.current === controller) pollingController.current = null;
      if (mounted.current) setCreating(false);
    }
  }

  async function loadBatchDetail(batchId: string) {
    setBusyBatchId(batchId);
    setError(null);
    try {
      setBatchDetail(await client.getBatch(batchId));
    } catch (cause) {
      setError(toMessage(cause));
    } finally {
      setBusyBatchId(null);
    }
  }

  async function download(batch: ExportBatch) {
    setBusyBatchId(batch.export_batch_id);
    setError(null);
    try {
      const blob = await client.downloadBatch(batch.export_batch_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = batch.download_name;
      link.rel = "noopener";
      link.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(toMessage(cause));
    } finally {
      setBusyBatchId(null);
    }
  }

  const reexportMode = filters.export_status === "REEXPORT_REQUIRED";
  const generatedBatch = task?.status === "SUCCEEDED"
    ? batches.find((batch) => batch.task_id === task.task_id)
    : undefined;
  const failedTask = task && ["FAILED", "CANCELLED", "INTERRUPTED"].includes(task.status);
  const quickSnapshot: PreviewSnapshot | null = quickPreview
    ? { result: quickPreview, filters: normalizeFilters(EMPTY_FILTERS), generation: -1 }
    : null;
  const summaryPreview = activeTab === "quick" ? quickPreview : preview;

  return (
    <main className="export-center">
      <header className="export-center-header">
        <div>
          <span className="eyebrow">模板驱动 · 可追溯</span>
          <h1>导出数据</h1>
          <p>选择并检查最终数据，生成 Excel，再从受控入口下载文件。</p>
        </div>
        <div className="export-center-summary" aria-label="导出摘要">
          <span><strong>{summaryPreview?.included.length ?? "—"}</strong> 拟包含</span>
          <span><strong>{summaryPreview?.excluded.length ?? "—"}</strong> 已排除</span>
          <span><strong>{batches.length}</strong> 导出记录</span>
        </div>
      </header>

      <nav className="export-mode-tabs" aria-label="导出方式" role="tablist">
        <button type="button" role="tab" aria-selected={activeTab === "quick"} className={activeTab === "quick" ? "active" : ""} onClick={() => setActiveTab("quick")}>快速导出</button>
        <button type="button" role="tab" aria-selected={activeTab === "custom"} className={activeTab === "custom" ? "active" : ""} onClick={() => setActiveTab("custom")}>自定义导出</button>
        <button type="button" role="tab" aria-selected={activeTab === "history"} className={activeTab === "history" ? "active" : ""} onClick={() => setActiveTab("history")}>导出记录</button>
      </nav>

      {activeTab === "quick" && (
        <section className="quick-export-card" aria-label="快速导出摘要">
          <div><span className="eyebrow">默认导出未导出的已确认记录</span><h2>可以导出 {quickPreview?.included.length ?? "—"} 条</h2><p>需要处理 {quickPreview?.excluded.length ?? "—"} 条</p></div>
          <div className="quick-export-actions">
            <button type="button" className="button button-secondary" disabled={quickPreviewing || creating} onClick={() => void loadQuickPreview()}>{quickPreviewing ? "正在检查…" : "刷新数量"}</button>
            <button type="button" className="button button-primary" disabled={!quickPreview?.included.length || !quickDefinition || creating} onClick={() => void createExport(undefined, quickSnapshot, quickDefinition?.report_key ?? "", false, quickDefinition?.definition_id)}>{creating ? "正在生成…" : "一键生成 Excel"}</button>
          </div>
        </section>
      )}

      {activeTab === "custom" && <nav className="export-steps" aria-label="导出步骤">
        <ol>
          <li><span>1</span><h2>选择数据</h2></li>
          <li><span>2</span><h2>检查数据</h2></li>
          <li><span>3</span><h2>生成并下载</h2></li>
        </ol>
      </nav>}

      {error && <ProblemNotice title="导出操作没有完成" reason={error} actionLabel="返回并重新检查数据" onAction={() => setError(null)} />}
      {message && <div className="success-banner export-center-message" role="status">{message}</div>}

      {activeTab !== "history" && (
        <aside className="report-assistant-card" aria-label="只读 AI 报表助手">
          <div>
            <span className="eyebrow">只读辅助 · 不会自动执行</span>
            <h2>AI 报表助手</h2>
            <p>可解释排除原因或推荐已有报表；所有建议仍由你确认。请勿输入姓名、工号或原图内容。</p>
          </div>
          <label>
            想了解什么？
            <textarea
              value={assistantQuestion}
              maxLength={1000}
              placeholder="例如：为什么有记录不能导出？应该选择哪种汇总报表？"
              onChange={(event) => setAssistantQuestion(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="button button-secondary"
            disabled={assistantBusy || !assistantQuestion.trim()}
            onClick={() => void askAssistant()}
          >{assistantBusy ? "正在分析…" : "询问 AI 助手"}</button>
          {assistantResult && (
            <div className="report-assistant-answer" role="status">
              <strong>{assistantResult.status === "READY" ? "临时建议" : "AI 暂时不可用"}</strong>
              <p>{assistantResult.answer}</p>
              {assistantResult.next_steps.length > 0 && (
                <ul>{assistantResult.next_steps.map((step) => <li key={step}>{step}</li>)}</ul>
              )}
              <small>本内容不会修改记录、模板或文件。</small>
            </div>
          )}
        </aside>
      )}

      {activeTab === "custom" && <section className="export-filter-card" aria-labelledby="export-filter-title">
        <div className="export-section-heading">
          <div>
            <span className="eyebrow">第一步 · 选择数据</span>
            <h2 id="export-filter-title">选择导出范围</h2>
          </div>
          <button
            type="button"
            className="button button-primary"
            disabled={previewing || creating}
            onClick={() => void loadPreview()}
          >
            {previewing ? "正在检查…" : "检查可导出的数据"}
          </button>
        </div>
        <div className="export-filter-grid">
          <label>表单编号<input disabled={creating} value={filters.form_id ?? ""} onChange={(event) => changeFilter("form_id", event.target.value)} /></label>
          <label>员工编号<input disabled={creating} value={filters.employee_id ?? ""} onChange={(event) => changeFilter("employee_id", event.target.value)} /></label>
          <label>工单编号<input disabled={creating} value={filters.work_order_id ?? ""} onChange={(event) => changeFilter("work_order_id", event.target.value)} /></label>
          <label>
            审核状态
            <select disabled={creating} value={filters.review_status ?? ""} onChange={(event) => changeFilter("review_status", event.target.value as ExportFilters["review_status"])}>
              <option value="">全部</option>
              <option value="CONFIRMED">已确认</option>
            </select>
          </label>
          <label>
            导出状态
            <select disabled={creating} value={filters.export_status === "REEXPORT_REQUIRED" ? "REEXPORT_REQUIRED" : "NOT_EXPORTED"} onChange={(event) => changeFilter("export_status", event.target.value as ExportFilters["export_status"])}>
              <option value="NOT_EXPORTED">未导出（普通新导出）</option>
              <option value="REEXPORT_REQUIRED">需要重导（选择来源记录）</option>
            </select>
          </label>
          <label>
            报表类型
            <select disabled={creating || !reportDefinitions.length} value={selectedDefinitionId} onChange={(event) => changeExportType(event.target.value)}>
              {reportDefinitions.map((definition) => (
                <option key={definition.definition_id} value={definition.definition_id}>
                  {definition.display_name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {needsRecheck && (
          <div className="export-recheck-notice" role="status">
            筛选条件已变化，请重新检查数据后再生成 Excel。
          </div>
        )}
        {reexportMode && (
          <div className="reexport-alert" role="alert">
            <strong>生成修正版</strong>
            <span>记录在上次导出后发生修改；选择包含旧数据的导出记录；系统生成修正版；旧文件继续保留。</span>
          </div>
        )}
      </section>}

      {activeTab === "custom" && preview && (
        <section className="export-preview-grid" aria-label="导出预览结果">
          <div className="export-preview-card included-records">
            <div className="export-section-heading compact">
              <div><span className="eyebrow">第二步 · 检查数据</span><h2>将要导出的记录</h2></div>
              <span className="status-pill active">{preview.included.length}</span>
            </div>
            {preview.included.length ? (
              <ul className="export-record-list">
                {preview.included.map((item) => <li key={`${item.form_id}-${item.record_version}`}>{item.form_id} · 记录版本 {item.record_version}</li>)}
              </ul>
            ) : <p className="muted">当前筛选没有可导出记录。</p>}
            <button
              type="button"
              className="button button-primary"
              disabled={!preview.included.length || creating || !selectedDefinition || reexportMode}
              onClick={() => void createExport()}
            >生成 Excel</button>
            {reexportMode && <small className="reexport-create-hint">重导必须从下方选择一个覆盖全部表单旧版本的来源记录。</small>}
          </div>

          <div className="export-preview-card" role="region" aria-label="无法导出的记录">
            <div className="export-section-heading compact">
              <div><span className="eyebrow">未进入文件</span><h2>无法导出的记录及原因</h2></div>
              <span className="status-pill inactive">{preview.excluded.length}</span>
            </div>
            {preview.excluded.length ? (
              <ul className="export-exclusion-list">
                {preview.excluded.map((item) => (
                  <li key={`${item.form_id}-${item.record_version}`}>
                    <strong>{item.form_id} · 记录版本 {item.record_version}</strong>
                    <ul>
                      {(item.reasons ?? []).map((reason, index) => (
                        <li key={`${reason.scope}-${reason.code}-${reason.field_key ?? index}`}>
                          <span className={`reason-scope ${reason.scope.toLowerCase()}`}>{reasonLabel(reason)}</span>
                          <p>{reasonMessage(reason)}</p>
                          {ruleDetail(reason) && <small>{ruleDetail(reason)}</small>}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">没有被排除的记录。</p>}
          </div>

          <div className="export-preview-card export-mappings">
            <div className="export-section-heading compact"><div><span className="eyebrow">生成前确认</span><h2>Excel 列对应关系</h2></div></div>
            <ul>
              {preview.mapping_snapshot.map((mapping) => (
                <li key={`${mapping.template_id}-${mapping.template_version}-${mapping.field_key}`}>
                  <strong>{mapping.worksheet}</strong>
                  <span>Excel 列：{mapping.business_column}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {activeTab !== "history" && task && (
        <section className="export-task-card" aria-live="polite">
          <div className="export-section-heading compact">
            <div><span className="eyebrow">第三步 · 生成并下载</span><h2>{exportTaskStatusLabel(task.status)}</h2></div>
            <strong>{task.progress}%</strong>
          </div>
          <progress value={task.progress} max={100} aria-label="导出任务进度" aria-valuenow={task.progress} />
          <span>{taskStepLabel(task.step)}</span>
          {failedTask && (
            <div className="export-task-failure" role="alert" aria-label="Excel 生成失败">
              <strong>本次 Excel 未生成</strong>
              <span>{task.error ?? "生成过程已中断，请重新生成。"}</span>
              <button
                type="button"
                className="button button-primary"
                disabled={creating || !preview}
                onClick={() => void createExport(lastSupersedesBatchId)}
              >重新生成 Excel</button>
            </div>
          )}
          {generatedBatch && (
            <button
              type="button"
              className="button button-primary export-download-ready"
              disabled={busyBatchId === generatedBatch.export_batch_id}
              onClick={() => void download(generatedBatch)}
            >下载刚生成的 Excel</button>
          )}
        </section>
      )}

      {activeTab === "history" && <section className="export-history-card" role="region" aria-label="导出记录">
        <div className="export-section-heading">
          <div><span className="eyebrow">独立记录区</span><h2>导出记录</h2></div>
          <button type="button" className="button button-secondary" onClick={() => void refreshBatches()}>刷新记录</button>
        </div>
        {batches.length ? (
          <div className="export-batch-list">
            {batches.map((batch) => {
              const canReexport = reexportMode && isEligibleSupersededBatch(batch, preview?.included ?? []);
              return (
                <article key={batch.export_batch_id} className={canReexport ? "reexport-source" : ""}>
                  <div>
                    <strong>导出记录 {shortBatchId(batch.export_batch_id)}</strong>
                    <span>工资记录 · {formatDate(batch.exported_at)} · {batch.included_records.length} 条</span>
                    {batch.supersedes_batch_id && <small>这是在旧文件基础上生成的修正版</small>}
                  </div>
                  <div className="export-batch-actions">
                    <button type="button" className="text-button" disabled={busyBatchId === batch.export_batch_id} onClick={() => void loadBatchDetail(batch.export_batch_id)}>打开记录 {shortBatchId(batch.export_batch_id)} 的追溯详情</button>
                    <button type="button" className="button button-secondary" disabled={busyBatchId === batch.export_batch_id} onClick={() => void download(batch)}>下载文件</button>
                    {canReexport && <button type="button" className="button button-primary" disabled={creating} onClick={() => void createExport(batch.export_batch_id)}>用此记录生成修正版</button>}
                    {reexportMode && !canReexport && <>
                      <button type="button" className="button button-secondary" disabled>此记录不可用于重导</button>
                      <small className="reexport-source-warning">该记录未包含每个拟重导表单的旧版本，请缩小筛选范围。</small>
                    </>}
                  </div>
                </article>
              );
            })}
          </div>
        ) : <p className="muted">尚无成功导出记录。</p>}
        {batchDetail && (
          <aside className="export-batch-detail" aria-label="追溯详情">
            <div className="export-section-heading compact">
              <div><span className="eyebrow">完整技术信息</span><h3>追溯详情</h3></div>
              <button type="button" className="text-button" onClick={() => setBatchDetail(null)}>关闭追溯详情</button>
            </div>
            <TraceDetails defaultOpen items={traceItems(batchDetail)} />
          </aside>
        )}
      </section>}
    </main>
  );
}

function reasonLabel(reason: ExportExclusionReason): string {
  return reason.scope === "FIELD" && reason.field_key
    ? `字段 ${reason.field_key}`
    : "整张表单";
}

function reasonMessage(reason: ExportExclusionReason): string {
  return ({
    NOT_CONFIRMED: "表单尚未完成确认。",
    TEMPLATE_NOT_FOUND: "找不到该表单使用的模板版本。",
    NO_VALID_MAPPING: "模板没有可用的 Excel 列对应关系。",
    FINAL_VALIDATION_FAILED: "记录未通过导出前的最终检查。",
    REQUIRED_VALUE_MISSING: "必填内容尚未填写。",
    NOT_ALLOWED: "填写内容不在模板允许范围内。",
    VALUE_NOT_ALLOWED: "填写内容不在模板允许范围内。",
    VALUE_NOT_NUMERIC: "填写内容必须是数字。",
    VALUE_BELOW_MINIMUM: "填写数值低于允许的最小值。",
    VALUE_ABOVE_MAXIMUM: "填写数值高于允许的最大值。",
  } as Record<string, string>)[reason.code] ?? reason.message;
}

function exportTaskStatusLabel(status: ExportTask["status"]): string {
  if (status === "RUNNING") return "正在生成 Excel";
  if (status === "SUCCEEDED") return "Excel 已生成";
  if (status === "PENDING") return "等待生成";
  return getTaskStatusCopy(status).label;
}

function taskStepLabel(step: string | null): string {
  return {
    PENDING: "正在排队",
    VALIDATING: "正在检查数据",
    WRITE_WORKBOOK: "正在写入工作表",
    COMPLETE: "文件已经可以下载",
  }[step ?? ""] ?? "正在处理导出数据";
}

function shortBatchId(batchId: string): string {
  return batchId.split("-").at(-1)?.slice(-8) || batchId.slice(-8);
}

function traceItems(batch: ExportBatch) {
  return [
    { label: "完整批次 ID", value: batch.export_batch_id },
    { label: "任务 ID", value: batch.task_id ?? "无" },
    { label: "操作者", value: batch.exported_by },
    { label: "映射哈希", value: batch.mapping_hash },
    { label: "文件哈希", value: batch.file_sha256 },
    { label: "内部文件名", value: batch.download_name },
    { label: "导出状态代码", value: batch.filters.export_status ?? "无" },
    { label: "替代批次", value: batch.supersedes_batch_id ?? "无" },
  ];
}

function normalizeFilters(filters: ExportFilters): ExportFilters {
  const normalized = Object.fromEntries(
    Object.entries(filters)
      .map(([key, value]) => [key, typeof value === "string" ? value.trim() : value])
      .filter(([, value]) => value !== undefined && value !== ""),
  ) as ExportFilters;
  normalized.export_status = filters.export_status === "REEXPORT_REQUIRED"
    ? "REEXPORT_REQUIRED"
    : "NOT_EXPORTED";
  return normalized;
}

function isEligibleSupersededBatch(
  batch: ExportBatch,
  included: ExportPreview["included"],
): boolean {
  return included.length > 0 && included.every((item) => (
    batch.included_records.some((record) => (
      record.form_id === item.form_id && record.record_version < item.record_version
    ))
  ));
}

function ruleDetail(reason: ExportExclusionReason): string | null {
  const details: string[] = [];
  if (reason.required) details.push("必填");
  if (reason.allowed_values?.length) details.push(`允许值：${reason.allowed_values.join("、")}`);
  if (reason.minimum_value !== undefined || reason.maximum_value !== undefined) {
    details.push(`范围：${reason.minimum_value ?? "—"}–${reason.maximum_value ?? "—"}`);
  }
  return details.length ? details.join("；") : null;
}

function makeIdempotencyKey(): string {
  const randomId = globalThis.crypto?.randomUUID?.();
  return `export-${randomId ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN");
}

function toMessage(cause: unknown): string {
  return businessErrorMessage(cause, "导出请求无法完成。");
}

function isAbortError(cause: unknown): boolean {
  return cause instanceof Error && cause.name === "AbortError";
}
