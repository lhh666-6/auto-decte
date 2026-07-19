export type ImportItemStatus = "QUEUED" | "PROCESSING" | "SUCCEEDED" | "NEEDS_ACTION" | "FAILED";

export interface ImportBatchItem {
  task_id: string;
  form_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  width: number;
  height: number;
  status: Exclude<ImportItemStatus, "QUEUED">;
  review_status: string | null;
  thumbnail_url: string | null;
  error: string | null;
}

export interface ImportBatchSummary {
  batch_id: string;
  created_at: string;
  counts: {
    total: number;
    succeeded: number;
    processing: number;
    needs_action: number;
    failed: number;
  };
  items: ImportBatchItem[];
}

export interface ImportedImageSummary {
  form_id: string;
  file_name: string;
  review_status: string;
  template_id: string;
  template_version: string;
  created_at: string;
  thumbnail_url: string;
  original_url: string;
}

export type UploadImageResult =
  | { status: "SUCCEEDED"; form_id: string; task_id: string }
  | { status: "NEEDS_ACTION"; form_id: string; task_id: string | null; detail: string };

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class ImportApi {
  constructor(
    private readonly baseUrl = "/api/v1",
    private readonly fetcher: Fetcher = fetch,
  ) {}

  async uploadImage(file: File, batchId: string, idempotencyKey: string): Promise<UploadImageResult> {
    const response = await this.fetcher(`${this.baseUrl}/imports`, {
      method: "POST",
      headers: {
        "Content-Type": file.type,
        "Idempotency-Key": idempotencyKey,
        "X-Import-Batch-ID": batchId,
        "X-Original-Filename": encodeURIComponent(file.name),
      },
      body: file,
    });
    const payload = await response.json() as {
      form_id?: string;
      task_id?: string | null;
      code?: string;
      detail?: string;
      existing_form?: { form_id: string };
    };
    if (response.status === 409 && payload.code === "DUPLICATE_EVIDENCE" && payload.existing_form) {
      return {
        status: "NEEDS_ACTION",
        form_id: payload.existing_form.form_id,
        task_id: payload.task_id ?? null,
        detail: payload.detail ?? "图片重复，已保留原表单。",
      };
    }
    if (!response.ok || !payload.form_id || !payload.task_id) {
      throw new Error(payload.detail ?? "图片导入失败。请重试。");
    }
    return { status: "SUCCEEDED", form_id: payload.form_id, task_id: payload.task_id };
  }

  listBatches(): Promise<ImportBatchSummary[]> {
    return this.get("/import-batches");
  }

  listImages(): Promise<ImportedImageSummary[]> {
    return this.get("/images");
  }

  private async get<T>(path: string): Promise<T> {
    const response = await this.fetcher(`${this.baseUrl}${path}`, { method: "GET" });
    if (!response.ok) throw new Error("图片资料读取失败，请重试。");
    return response.json() as Promise<T>;
  }
}
