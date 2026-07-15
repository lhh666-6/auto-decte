export interface FormSummary {
  form_id: string;
  template_id: string;
  template_version: string;
  coordinate_version: string;
  review_status: string;
  export_status: string;
  current_record_version: number;
  priority: number;
  created_at: string;
}

export interface RecognitionCandidate {
  attempt_id: string;
  candidate_value: unknown;
  confidence: number;
  engine: string;
  model_version: string;
  crop_file_id: string;
}

export interface ReviewField {
  field_id: string;
  field_name: string;
  recognition_engine: string | null;
  source_region: Record<string, number>;
  current_value: unknown;
  current_value_source: string | null;
  current_record_version: number;
  candidates: RecognitionCandidate[];
}

export interface EvidenceItem {
  file_id: string;
  type: string;
  related_field_id: string | null;
  sha256: string;
  immutable: boolean;
  created_at: string;
  download_url: string;
}

export interface RecordVersion {
  record_id: string;
  version: number;
  previous_version: number | null;
  status: string;
  values: Record<string, unknown>;
  change_reason: string;
  confirmed_by: string | null;
  created_at: string;
}

export interface AuditEvent {
  event_id: string;
  event_type: string;
  actor_id: string;
  timestamp: string;
  reason: string | null;
  evidence_ids: string[];
}

export interface WorkbenchDetail {
  form: FormSummary;
  fields: ReviewField[];
  evidence: EvidenceItem[];
  current_record: RecordVersion | null;
  draft: ReviewDraft | null;
}

export interface ReviewDraft {
  expected_version: number;
  values: Record<string, unknown>;
  saved_by: string;
  updated_at: string;
}

export interface ReviewHistory {
  versions: RecordVersion[];
  audits: AuditEvent[];
}

export interface ReviewLease {
  form_id: string;
  owner_id: string;
  lease_token: string;
  expires_at: string;
}

export interface ClassificationOption {
  template_key: string;
  version: number;
  field_count: number;
  page_size: string;
  orientation: string;
}

export interface ConfirmAndClaimNextResult {
  record: { record_id: string; version: number; status: string };
  next: { workbench: WorkbenchDetail; lease: ReviewLease } | null;
}

interface ReviewVersionInput {
  expectedVersion: number;
  leaseToken: string;
}

interface ReviewActionInput extends ReviewVersionInput {
  reason: string;
  evidenceIds: string[];
}

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class ReviewWorkbenchApi {
  constructor(
    private readonly baseUrl = "/api/v1",
    private readonly fetcher: Fetcher = fetch,
  ) {}

  getWorkbench(formId: string): Promise<WorkbenchDetail> {
    return this.request(`/forms/${encodeURIComponent(formId)}`);
  }

  getQueue(queueKey: "classification" | "review" | "exceptions" | "exportable"): Promise<FormSummary[]> {
    return this.request(`/forms/queue/${queueKey}`);
  }

  getHistory(formId: string): Promise<ReviewHistory> {
    return this.request(`/forms/${encodeURIComponent(formId)}/review-history`);
  }

  acquireLease(formId: string): Promise<ReviewLease> {
    return this.request(`/forms/${encodeURIComponent(formId)}/review-lease`, { method: "POST" });
  }

  heartbeatLease(formId: string, leaseToken: string): Promise<ReviewLease> {
    return this.request(`/forms/${encodeURIComponent(formId)}/review-lease/heartbeat`, {
      method: "POST",
      body: { lease_token: leaseToken },
    });
  }

  async releaseLease(formId: string, leaseToken: string): Promise<void> {
    await this.request<void>(`/forms/${encodeURIComponent(formId)}/review-lease`, {
      method: "DELETE",
      body: { lease_token: leaseToken },
    });
  }

  confirm(
    formId: string,
    input: {
      expectedVersion: number;
      leaseToken: string;
      values: Record<string, unknown>;
      reason: string;
      evidenceIds: string[];
    },
  ): Promise<{ record_id: string; version: number; status: string }> {
    return this.request(`/forms/${encodeURIComponent(formId)}/confirm`, {
      method: "POST",
      headers: { "If-Match": String(input.expectedVersion) },
      body: {
        expected_version: input.expectedVersion,
        lease_token: input.leaseToken,
        values: input.values,
        reason: input.reason,
        evidence_ids: input.evidenceIds,
      },
    });
  }

  saveDraft(
    formId: string,
    input: ReviewVersionInput & { values: Record<string, unknown> },
  ): Promise<ReviewDraft> {
    return this.request(`/forms/${encodeURIComponent(formId)}/review-draft`, {
      method: "PUT",
      body: {
        expected_version: input.expectedVersion,
        lease_token: input.leaseToken,
        values: input.values,
      },
    });
  }

  returnForm(
    formId: string,
    input: ReviewActionInput,
  ): Promise<{ form_id: string; review_status: string }> {
    return this.reviewAction(formId, "return", input);
  }

  voidForm(
    formId: string,
    input: ReviewActionInput,
  ): Promise<{ record_id: string; version: number; status: string }> {
    return this.reviewAction(formId, "void", input);
  }

  confirmAndClaimNext(
    formId: string,
    input: ReviewActionInput & {
      values: Record<string, unknown>;
      queueKey: "review";
    },
  ): Promise<ConfirmAndClaimNextResult> {
    return this.request(`/forms/${encodeURIComponent(formId)}/confirm-and-claim-next`, {
      method: "POST",
      headers: { "If-Match": String(input.expectedVersion) },
      body: {
        expected_version: input.expectedVersion,
        lease_token: input.leaseToken,
        values: input.values,
        reason: input.reason,
        evidence_ids: input.evidenceIds,
        queue_key: input.queueKey,
      },
    });
  }

  getClassificationOptions(formId: string): Promise<ClassificationOption[]> {
    return this.request(`/forms/${encodeURIComponent(formId)}/classification-options`);
  }

  assignTemplate(
    formId: string,
    input: { templateKey: string; version: number; reason: string },
  ): Promise<{
    form_id: string;
    template_key: string;
    template_version: number;
    review_status: string;
    recognition_task_id: string;
    recognition_task_status: string;
  }> {
    return this.request(`/forms/${encodeURIComponent(formId)}/assign-template`, {
      method: "POST",
      body: {
        template_key: input.templateKey,
        version: input.version,
        reason: input.reason,
      },
    });
  }

  private reviewAction<T>(
    formId: string,
    action: "return" | "void",
    input: ReviewActionInput,
  ): Promise<T> {
    return this.request(`/forms/${encodeURIComponent(formId)}/${action}`, {
      method: "POST",
      headers: { "If-Match": String(input.expectedVersion) },
      body: {
        expected_version: input.expectedVersion,
        lease_token: input.leaseToken,
        reason: input.reason,
        evidence_ids: input.evidenceIds,
      },
    });
  }

  private async request<T>(
    path: string,
    options: { method?: string; headers?: Record<string, string>; body?: unknown } = {},
  ): Promise<T> {
    const headers = { ...options.headers };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    const fetcher = this.fetcher;
    const response = await fetcher(`${this.baseUrl}${path}`, {
      method: options.method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    if (response.status === 204) {
      return undefined as T;
    }
    if (!response.ok) {
      const problem = (await response.json().catch(() => ({}))) as {
        code?: string;
        detail?: string;
      };
      throw new ApiRequestError(
        response.status,
        problem.code ?? "REQUEST_FAILED",
        problem.detail ?? `Request failed with status ${response.status}`,
      );
    }
    return (await response.json()) as T;
  }
}
