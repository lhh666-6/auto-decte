import {
  ApiRequestError,
  ExportApi,
  type CreateExportInput,
  type CreateExportResponse,
  type ExportBatch,
  type ExportExclusionReason,
  type ExportFilters,
  type ExportPreview,
  type ExportTask,
  type WaitForExportTaskOptions,
} from "@form-detection/api-client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface ExportCenterApi {
  preview(filters: ExportFilters, signal?: AbortSignal): Promise<ExportPreview>;
  create(input: CreateExportInput, idempotencyKey: string): Promise<CreateExportResponse>;
  waitForTask(taskId: string, options?: WaitForExportTaskOptions): Promise<ExportTask>;
  listBatches(): Promise<ExportBatch[]>;
  getBatch(batchId: string): Promise<ExportBatch>;
  downloadBatch(batchId: string): Promise<Blob>;
}

interface ExportCenterProps {
  api?: ExportCenterApi;
  onBack: () => void;
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

export function ExportCenter({ api, onBack }: ExportCenterProps) {
  const client = useMemo<ExportCenterApi>(() => api ?? new ExportApi("/api/v1"), [api]);
  const [filters, setFilters] = useState<ExportFilters>(EMPTY_FILTERS);
  const [exportType, setExportType] = useState("PAYROLL");
  const [previewSnapshot, setPreviewSnapshot] = useState<PreviewSnapshot | null>(null);
  const [batches, setBatches] = useState<ExportBatch[]>([]);
  const [batchDetail, setBatchDetail] = useState<ExportBatch | null>(null);
  const [task, setTask] = useState<ExportTask | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [busyBatchId, setBusyBatchId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  const pollingController = useRef<AbortController | null>(null);
  const previewController = useRef<AbortController | null>(null);
  const previewGeneration = useRef(0);
  const batchGeneration = useRef(0);
  const preview = previewSnapshot?.result ?? null;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      pollingController.current?.abort();
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

  function changeFilter<K extends keyof ExportFilters>(key: K, value: ExportFilters[K]) {
    const nextValue = key === "export_status"
      ? value === "REEXPORT_REQUIRED" ? value : "NOT_EXPORTED"
      : value || undefined;
    previewController.current?.abort();
    previewController.current = null;
    previewGeneration.current += 1;
    setFilters((current) => ({ ...current, [key]: nextValue }));
    setPreviewSnapshot(null);
    setPreviewing(false);
    setMessage(null);
  }

  function changeExportType(value: string) {
    previewController.current?.abort();
    previewController.current = null;
    previewGeneration.current += 1;
    setExportType(value);
    setPreviewSnapshot(null);
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

  async function createExport(supersedesBatchId?: string) {
    const activePreview = previewSnapshot;
    if (
      !activePreview?.result.included.length ||
      activePreview.generation !== previewGeneration.current ||
      !exportType.trim()
    ) return;
    if (activePreview.filters.export_status === "REEXPORT_REQUIRED" && !supersedesBatchId) return;
    setCreating(true);
    setError(null);
    setMessage(null);
    setTask(null);
    pollingController.current?.abort();
    const controller = new AbortController();
    pollingController.current = controller;
    try {
      const created = await client.create({
        export_type: exportType.trim(),
        filters: activePreview.filters,
        ...(supersedesBatchId ? { supersedes_batch_id: supersedesBatchId } : {}),
      }, makeIdempotencyKey());
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
        setMessage("导出任务已完成。");
        await refreshBatches();
      } else {
        setError(completed.error ?? `导出任务终止：${completed.status}`);
      }
    } catch (cause) {
      if (!isAbortError(cause) && mounted.current) setError(toMessage(cause));
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

  async function copyTrace(batch: ExportBatch) {
    try {
      await navigator.clipboard?.writeText(traceText(batch));
      setMessage("追溯信息已复制。");
    } catch {
      setError("无法访问剪贴板，请手动复制追溯信息。");
    }
  }

  const reexportMode = filters.export_status === "REEXPORT_REQUIRED";

  return (
    <main className="export-center">
      <header className="export-center-header">
        <div>
          <button type="button" className="text-button" onClick={onBack}>← 返回审核工作台</button>
          <span className="eyebrow">模板驱动 · 可追溯</span>
          <h1>导出中心</h1>
          <p>预览最终校验结果，创建异步 XLSX 任务并从授权接口下载。</p>
        </div>
        <div className="export-center-summary" aria-label="导出摘要">
          <span><strong>{preview?.included.length ?? "—"}</strong> 拟包含</span>
          <span><strong>{preview?.excluded.length ?? "—"}</strong> 已排除</span>
          <span><strong>{batches.length}</strong> 历史批次</span>
        </div>
      </header>

      <nav className="export-steps" aria-label="导出步骤">
        <ol>
          <li><span>1</span><h2>选择数据</h2></li>
          <li><span>2</span><h2>检查数据</h2></li>
          <li><span>3</span><h2>生成 Excel</h2></li>
          <li><span>4</span><h2>下载文件</h2></li>
        </ol>
      </nav>

      {error && <div className="error-banner export-center-message" role="alert">{error}</div>}
      {message && <div className="success-banner export-center-message" role="status">{message}</div>}

      <section className="export-filter-card" aria-labelledby="export-filter-title">
        <div className="export-section-heading">
          <div>
            <span className="eyebrow">第一步</span>
            <h2 id="export-filter-title">筛选条件</h2>
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
          <label>表单编号<input value={filters.form_id ?? ""} onChange={(event) => changeFilter("form_id", event.target.value)} /></label>
          <label>员工编号<input value={filters.employee_id ?? ""} onChange={(event) => changeFilter("employee_id", event.target.value)} /></label>
          <label>工单编号<input value={filters.work_order_id ?? ""} onChange={(event) => changeFilter("work_order_id", event.target.value)} /></label>
          <label>
            审核状态
            <select value={filters.review_status ?? ""} onChange={(event) => changeFilter("review_status", event.target.value as ExportFilters["review_status"])}>
              <option value="">全部</option>
              <option value="CONFIRMED">已确认</option>
            </select>
          </label>
          <label>
            导出状态
            <select value={filters.export_status === "REEXPORT_REQUIRED" ? "REEXPORT_REQUIRED" : "NOT_EXPORTED"} onChange={(event) => changeFilter("export_status", event.target.value as ExportFilters["export_status"])}>
              <option value="NOT_EXPORTED">未导出（普通新导出）</option>
              <option value="REEXPORT_REQUIRED">需要重导（选择来源批次）</option>
            </select>
          </label>
          <label>
            文件用途
            <select value={exportType} onChange={(event) => changeExportType(event.target.value)}>
              <option value="PAYROLL">工资记录</option>
            </select>
          </label>
        </div>
        {reexportMode && (
          <div className="reexport-alert" role="alert">
            <strong>生成修正版</strong>
            <span>记录在上次导出后发生修改；选择包含旧数据的导出记录；系统生成修正版；旧文件继续保留。</span>
          </div>
        )}
      </section>

      {preview && (
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
              disabled={!preview.included.length || creating || !exportType.trim() || reexportMode}
              onClick={() => void createExport()}
            >生成 Excel</button>
            {reexportMode && <small className="reexport-create-hint">重导必须从下方选择一个覆盖全部表单旧版本的来源批次。</small>}
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
                          <p>{reason.message}</p>
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
                  <strong>{mapping.field_key}</strong>
                  <span>{mapping.workbook} / {mapping.worksheet} / {mapping.business_column}</span>
                  <small>{mapping.template_id} · V{mapping.template_version}</small>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {task && (
        <section className="export-task-card" aria-live="polite">
          <div className="export-section-heading compact">
            <div><span className="eyebrow">第三步 · 生成进度</span><h2>{taskStatusLabel(task.status)}</h2></div>
            <strong>{task.progress}%</strong>
          </div>
          <progress value={task.progress} max={100} aria-label="导出任务进度" aria-valuenow={task.progress} />
          <span>{taskStepLabel(task.step)}</span>
        </section>
      )}

      <section className="export-history-card" role="region" aria-label="导出批次历史">
        <div className="export-section-heading">
          <div><span className="eyebrow">第四步 · 下载文件</span><h2>导出历史</h2></div>
          <button type="button" className="button button-secondary" onClick={() => void refreshBatches()}>刷新历史</button>
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
                      <small className="reexport-source-warning">该批次未包含每个拟重导表单的旧版本，请缩小筛选范围。</small>
                    </>}
                  </div>
                </article>
              );
            })}
          </div>
        ) : <p className="muted">尚无成功导出批次。</p>}
        {batchDetail && (
          <aside className="export-batch-detail" aria-label="追溯详情">
            <div className="export-section-heading compact">
              <div><span className="eyebrow">完整技术信息</span><h3>追溯详情</h3></div>
              <button type="button" className="text-button" onClick={() => setBatchDetail(null)}>关闭追溯详情</button>
            </div>
            <dl>
              <div><dt>完整批次 ID</dt><dd>{batchDetail.export_batch_id}</dd></div>
              <div><dt>任务 ID</dt><dd>{batchDetail.task_id ?? "无"}</dd></div>
              <div><dt>操作者</dt><dd>{batchDetail.exported_by}</dd></div>
              <div><dt>映射哈希</dt><dd>{batchDetail.mapping_hash}</dd></div>
              <div><dt>文件哈希</dt><dd>{batchDetail.file_sha256}</dd></div>
              <div><dt>内部文件名</dt><dd>{batchDetail.download_name}</dd></div>
              <div><dt>导出状态代码</dt><dd>{batchDetail.filters.export_status ?? "无"}</dd></div>
              <div><dt>替代批次</dt><dd>{batchDetail.supersedes_batch_id ?? "无"}</dd></div>
            </dl>
            <button type="button" className="button button-secondary" onClick={() => void copyTrace(batchDetail)}>复制追溯信息</button>
          </aside>
        )}
      </section>
    </main>
  );
}

function reasonLabel(reason: ExportExclusionReason): string {
  return reason.scope === "FIELD" && reason.field_key
    ? `字段 ${reason.field_key}`
    : "整张表单";
}

function taskStatusLabel(status: ExportTask["status"]): string {
  return {
    PENDING: "等待生成",
    RUNNING: "正在生成 Excel",
    SUCCEEDED: "Excel 已生成",
    FAILED: "生成失败",
    CANCEL_REQUESTED: "正在取消",
    CANCELLED: "已取消",
    INTERRUPTED: "生成已中断",
    RECOVERING: "正在恢复生成",
  }[status];
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

function traceText(batch: ExportBatch): string {
  return [
    `完整批次 ID: ${batch.export_batch_id}`,
    `任务 ID: ${batch.task_id ?? "无"}`,
    `映射哈希: ${batch.mapping_hash}`,
    `文件哈希: ${batch.file_sha256}`,
    `内部文件名: ${batch.download_name}`,
    `导出状态代码: ${batch.filters.export_status ?? "无"}`,
    `替代批次: ${batch.supersedes_batch_id ?? "无"}`,
  ].join("\n");
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
  if (cause instanceof ApiRequestError) return cause.message;
  return cause instanceof Error ? cause.message : "导出请求无法完成。";
}

function isAbortError(cause: unknown): boolean {
  return cause instanceof Error && cause.name === "AbortError";
}
