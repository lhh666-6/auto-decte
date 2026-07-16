import { ApiRequestError } from "./review-workbench.js";

export type ExportStatus = "NOT_EXPORTED" | "EXPORTED" | "REEXPORT_REQUIRED";
export type ExportReviewStatus =
  | "IMPORTED"
  | "RECAPTURE_REQUIRED"
  | "CLASSIFIED"
  | "NEEDS_CLASSIFICATION"
  | "RECOGNIZED"
  | "NEEDS_REVIEW"
  | "AUTO_APPROVED"
  | "CONFIRMED"
  | "CORRECTED"
  | "SUPERSEDED"
  | "VOIDED";

export interface ExportFilters {
  form_id?: string;
  employee_id?: string;
  work_order_id?: string;
  review_status?: ExportReviewStatus;
  export_status?: ExportStatus;
}

export interface ExportExclusionReason {
  scope: "FORM" | "FIELD";
  code: string;
  field_key?: string;
  message: string;
  required?: boolean;
  allowed_values?: string[];
  minimum_value?: number;
  maximum_value?: number;
}

export interface ExportPreviewItem {
  form_id: string;
  record_version: number;
  reason?: string;
  reasons?: ExportExclusionReason[];
}

export interface ExportMapping {
  template_id: string;
  template_version: string;
  field_key: string;
  workbook: string;
  worksheet: string;
  business_column: string;
}

export interface ExportPreview {
  included: ExportPreviewItem[];
  excluded: ExportPreviewItem[];
  mapping_snapshot: ExportMapping[];
}

export interface CreateExportInput {
  export_type: string;
  filters: ExportFilters;
  supersedes_batch_id?: string;
}

export interface CreateExportResponse {
  task_id: string;
  status: ExportTaskStatus;
  status_url: string;
  events_url: string;
}

export type ExportTaskStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCEL_REQUESTED"
  | "CANCELLED"
  | "INTERRUPTED"
  | "RECOVERING";

export interface ExportTask {
  task_id: string;
  operation: "XLSX_EXPORT";
  resource_id: "EXPORTS";
  status: ExportTaskStatus;
  progress: number;
  step: string | null;
  error: string | null;
}

export interface IncludedExportRecord {
  form_id: string;
  record_version: number;
}

export interface ExportBatch {
  export_batch_id: string;
  export_type: string;
  task_id: string | null;
  template_snapshot: Record<string, unknown>;
  mapping_snapshot: ExportMapping[];
  mapping_hash: string;
  filters: ExportFilters;
  included_records: IncludedExportRecord[];
  file_sha256: string;
  exported_by: string;
  exported_at: string;
  supersedes_batch_id: string | null;
  download_url: string;
  download_name: string;
}

export interface WaitForExportTaskOptions {
  intervalMs?: number;
  signal?: AbortSignal;
  onUpdate?: (task: ExportTask) => void;
}

export interface ExportApiRequestDefaults {
  credentials?: RequestCredentials;
  headers?: Record<string, string>;
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

const TERMINAL_TASK_STATUSES = new Set<ExportTaskStatus>([
  "SUCCEEDED",
  "FAILED",
  "CANCELLED",
  "INTERRUPTED",
]);

export class ExportApi {
  constructor(
    private readonly baseUrl = "/api/v1",
    private readonly fetcher: Fetcher = fetch,
    private readonly defaults: ExportApiRequestDefaults = {},
  ) {}

  preview(filters: ExportFilters): Promise<ExportPreview> {
    const query = new URLSearchParams();
    const cleaned = cleanFilters(filters);
    for (const key of [
      "form_id",
      "employee_id",
      "work_order_id",
      "review_status",
      "export_status",
    ] as const) {
      const value = cleaned[key];
      if (value !== undefined) query.set(key, value);
    }
    const suffix = query.size > 0 ? `?${query.toString()}` : "";
    return this.request(`/exports/preview${suffix}`, { method: "GET" });
  }

  create(input: CreateExportInput, idempotencyKey: string): Promise<CreateExportResponse> {
    return this.request("/exports", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: {
        export_type: input.export_type,
        filters: cleanFilters(input.filters),
        ...(input.supersedes_batch_id
          ? { supersedes_batch_id: input.supersedes_batch_id }
          : {}),
      },
    });
  }

  getTask(taskId: string, signal?: AbortSignal): Promise<ExportTask> {
    return this.request(`/tasks/${encodeURIComponent(taskId)}`, { method: "GET", signal });
  }

  async waitForTask(
    taskId: string,
    options: WaitForExportTaskOptions = {},
  ): Promise<ExportTask> {
    const intervalMs = options.intervalMs ?? 750;
    while (true) {
      if (options.signal?.aborted) throw abortError();
      const task = await this.getTask(taskId, options.signal);
      options.onUpdate?.(task);
      if (TERMINAL_TASK_STATUSES.has(task.status)) return task;
      if (intervalMs > 0) await wait(intervalMs, options.signal);
    }
  }

  listBatches(): Promise<ExportBatch[]> {
    return this.request("/exports/batches", { method: "GET" });
  }

  getBatch(batchId: string): Promise<ExportBatch> {
    return this.request(`/exports/batches/${encodeURIComponent(batchId)}`, { method: "GET" });
  }

  async downloadBatch(batchId: string): Promise<Blob> {
    const response = await this.fetchResponse(
      `/exports/batches/${encodeURIComponent(batchId)}/download`,
      { method: "GET" },
    );
    return response.blob();
  }

  private async request<T>(
    path: string,
    options: { method?: string; headers?: Record<string, string>; body?: unknown; signal?: AbortSignal } = {},
  ): Promise<T> {
    const response = await this.fetchResponse(path, options);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  private async fetchResponse(
    path: string,
    options: { method?: string; headers?: Record<string, string>; body?: unknown; signal?: AbortSignal },
  ): Promise<Response> {
    const headers = { ...this.defaults.headers, ...options.headers };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    const fetcher = this.fetcher;
    const response = await fetcher(`${this.baseUrl}${path}`, {
      method: options.method,
      credentials: this.defaults.credentials ?? "same-origin",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      ...(options.signal ? { signal: options.signal } : {}),
    });
    if (!response.ok) await throwApiError(response);
    return response;
  }
}

function cleanFilters(filters: ExportFilters): ExportFilters {
  return Object.fromEntries(
    Object.entries(filters)
      .map(([key, value]) => [key, typeof value === "string" ? value.trim() : value])
      .filter(([, value]) => value !== undefined && value !== ""),
  ) as ExportFilters;
}

async function throwApiError(response: Response): Promise<never> {
  const problem = await response.json().catch(() => ({})) as {
    code?: string;
    detail?: string | { code?: string; detail?: string };
  };
  const nested = typeof problem.detail === "object" ? problem.detail : undefined;
  const detail = typeof problem.detail === "string"
    ? problem.detail
    : nested?.detail ?? `Request failed with status ${response.status}`;
  throw new ApiRequestError(
    response.status,
    problem.code ?? nested?.code ?? "REQUEST_FAILED",
    detail,
  );
}

function wait(milliseconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError());
      return;
    }
    const finish = () => {
      signal?.removeEventListener("abort", cancel);
      resolve();
    };
    const timer = globalThis.setTimeout(finish, milliseconds);
    const cancel = () => {
      globalThis.clearTimeout(timer);
      reject(abortError());
    };
    signal?.addEventListener("abort", cancel, { once: true });
  });
}

function abortError(): DOMException {
  return new DOMException("Export task polling was cancelled.", "AbortError");
}
