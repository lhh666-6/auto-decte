export interface MobileProblem {
  title: string;
  status: number;
  code: string;
  detail: string;
  request_id: string;
  failures?: unknown;
}

export class MobileApiError extends Error {
  constructor(public readonly problem: MobileProblem) {
    super(problem.detail);
    this.name = "MobileApiError";
  }

  get status(): number {
    return this.problem.status;
  }

  get code(): string {
    return this.problem.code;
  }
}

export interface MobileLoginResponse {
  employee_name: string;
  employee_code: string;
  team_name: string;
  position: string;
  roles: string[];
  expires_at: string | null;
  factory_id: string;
  factory_name: string;
  bamboo_role: string;
}

export interface MobileSession {
  employee_name: string;
  employee_code: string;
  team_name: string;
  position: string;
  roles: string[];
  allowed_form_types: string[];
  allowed_processes: string[];
  factory_id: string;
  factory_name: string;
  bamboo_role: string;
}

export type BambooStage = "SORT" | "DIPPING" | "DRYING" | "SUPERVISOR" | "PLANT_AUDIT";
export type BambooTaskBucket = "available" | "waiting" | "completed";

export interface BambooStageSubmission {
  submission_id: string;
  stage: BambooStage;
  version: number;
  values: Record<string, unknown>;
  actor_id: string;
  actor_name: string;
  role_code: string;
  submitted_at: string | null;
}

export interface BambooRecord {
  record_id: string;
  display_no: string;
  factory_id: string;
  source_type: string;
  source_ref: string | null;
  base_info: Record<string, unknown>;
  current_stage: BambooStage | null;
  status: "ACTIVE" | "COMPLETED";
  revision: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  submissions: BambooStageSubmission[];
}

export interface BambooDashboard {
  available: number;
  waiting: number;
  completed: number;
}

export interface SubmitBambooStageInput {
  expected_revision: number;
  device_id: string;
  values: Record<string, unknown>;
}

export interface BambooEvidence {
  asset_id: string;
  evidence_type: "PHOTO" | "AUDIO" | "TEXT";
  uri: string | null;
  text_content: string | null;
}

export interface BambooInspection {
  inspection_id: string;
  serial_no: string;
  target_stage: BambooStage;
  moisture_points: string[];
  average_value: string;
  conclusion: string;
  note: string | null;
  actor_name: string;
  evidence: BambooEvidence[];
  exception: null | {
    exception_id: string;
    status: "OPEN" | "CLOSED";
    resolution: string | null;
  };
}

export interface BambooPayrollFact {
  fact_id: string;
  fact_type: "SORT" | "DIPPING_DRYING_JOINT";
  version: number;
  status: "PENDING_EFFECTIVE" | "EFFECTIVE" | "INVALIDATED";
  rule_version_id: string;
  allocations: Array<{ employee_code: string; role: string; amount: string }>;
  total_amount: string;
}

export interface BambooOperationsSummary {
  payroll_facts: BambooPayrollFact[];
  inspections: BambooInspection[];
  corrections: Array<{ case_id: string; status: string; reason: string }>;
}

export interface BambooFinanceItem {
  item_id: string;
  record_id: string;
  employee_code: string;
  amount: string;
  status: string;
  revision: number;
}

export interface BambooDailyBatch {
  batch_id: string;
  business_date: string;
  version: number;
  status: string;
  supplemental: boolean;
  items: BambooFinanceItem[];
}

export interface BambooRoleChange {
  request_id: string;
  employee_code: string;
  from_role: string;
  to_role: string;
  reason: string;
  status: string;
}

export interface MobileAvailableForm {
  form_type: string;
  title: string;
  modes: string[];
  definition_version_id: string;
  allowed_processes: string[] | null;
}

export interface MobileFormField {
  field_name: string;
  field_type: string;
  label: string;
  strategy: string;
  source: string;
  required: boolean;
  preset_options: string[] | null;
  default_value: unknown;
  editable: boolean;
  input_type: string;
}

export interface MobileFormSchema {
  form_type: string;
  title: string;
  modes: string[];
  definition_version_id: string;
  version: string;
  fields: MobileFormField[];
}

export interface MobileContext {
  employee_name: string;
  employee_code: string;
  team_name: string;
  position: string;
  server_time: string;
  server_date: string;
  suggested_shift: string;
  roles: string[];
}

export interface MobileOption {
  value: string;
  label: string;
}

export interface MobileActiveResource {
  resource_id: string;
  short_code: string;
  variety: string;
  grade: string;
  supplier: string;
  current_status: string;
  last_process: string;
  last_process_time: string;
}

export interface MobileProductionContext {
  context_id: string;
  team_id: string;
  date: string;
  shift: string;
  work_orders: string[];
  products: string[];
  specs: string[];
  pieces_per_block: number | null;
}

export interface MobileSubmissionInput {
  form_type: string;
  definition_version_id: string;
  mode: "SELF" | "TEAM_LEADER_BATCH";
  subject_employee_code: string;
  device_id: string;
  values: Record<string, unknown>;
}

export interface MobileSubmissionReceipt {
  submission_id: string;
  status: string;
  submitted_at: string;
  idempotent: boolean;
}

export interface MobileSubmissionListItem {
  submission_id: string;
  form_id: string | null;
  subject_employee_code: string;
  status: string;
  submitted_at: string;
  idempotency_key: string;
}

export interface MobileTeamMember {
  employee_code: string;
  employee_name: string;
}

export type MobileFetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

type CsrfTokenReader = () => string | null;

function csrfTokenFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const prefix = "mobile_csrf=";
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

function isUnsafeMethod(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

async function toProblem(response: Response): Promise<MobileProblem> {
  const body = await response.json().catch(() => ({})) as Record<string, unknown>;
  const nested = typeof body.detail === "object" && body.detail !== null
    ? body.detail as Record<string, unknown>
    : body;
  const detail = typeof nested.detail === "string"
    ? nested.detail
    : typeof body.detail === "string"
      ? body.detail
      : response.statusText || "请求失败";
  return {
    title: typeof body.title === "string" ? body.title : response.statusText || "请求失败",
    status: response.status,
    code: typeof nested.code === "string" ? nested.code : `HTTP_${response.status}`,
    detail,
    request_id: typeof body.request_id === "string"
      ? body.request_id
      : response.headers.get("X-Request-ID") ?? "",
    failures: nested.failures,
  };
}

export class MobileApiClient {
  constructor(
    private readonly baseUrl = "/api/v1/mobile",
    private readonly fetcher: MobileFetcher = (input, init) => fetch(input, init),
    private readonly readCsrfToken: CsrfTokenReader = csrfTokenFromCookie,
  ) {}

  async fetchResponse(path: string, init: RequestInit = {}): Promise<Response> {
    const method = init.method ?? "GET";
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body != null && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (isUnsafeMethod(method) && path !== "/auth/login") {
      const csrfToken = this.readCsrfToken();
      if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
    }
    return this.fetcher(`${this.baseUrl}${path}`, {
      ...init,
      method,
      headers,
      credentials: "same-origin",
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.fetchResponse(path, init);
    if (!response.ok) throw new MobileApiError(await toProblem(response));
    return response.json() as Promise<T>;
  }

  login(employeeCode: string, pin: string, deviceId = "unknown"): Promise<MobileLoginResponse> {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ employee_code: employeeCode, pin, device_id: deviceId }),
    });
  }

  async logout(): Promise<void> {
    const response = await this.fetchResponse("/auth/logout", { method: "POST" });
    if (!response.ok) throw new MobileApiError(await toProblem(response));
  }

  getSession(): Promise<MobileSession> {
    return this.request("/auth/session");
  }

  getAvailableForms(): Promise<{ forms: MobileAvailableForm[] }> {
    return this.request("/available-forms");
  }

  getFormSchema(formType: string): Promise<MobileFormSchema> {
    return this.request(`/form-schemas/${encodeURIComponent(formType)}`);
  }

  getOptions(catalog: string): Promise<{ option_set: string; options: MobileOption[] }> {
    return this.request(`/options/${encodeURIComponent(catalog)}`);
  }

  getContext(): Promise<MobileContext> {
    return this.request("/context");
  }

  getActiveResources(resourceType = "CAGE", process = ""): Promise<{ resources: MobileActiveResource[] }> {
    const params = new URLSearchParams({ resource_type: resourceType });
    if (process) params.set("process", process);
    return this.request(`/active-resources?${params.toString()}`);
  }

  getProductionContext(): Promise<MobileProductionContext> {
    return this.request("/production-contexts/current");
  }

  getTeamMembers(): Promise<{ members: MobileTeamMember[] }> {
    return this.request("/team-members");
  }

  saveDraft(input: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request("/drafts", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  createSubmission(
    input: MobileSubmissionInput,
    idempotencyKey: string,
  ): Promise<MobileSubmissionReceipt> {
    return this.request("/submissions", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(input),
    });
  }

  listSubmissions(): Promise<{ submissions: MobileSubmissionListItem[] }> {
    return this.request("/submissions");
  }

  getBambooDashboard(): Promise<BambooDashboard> {
    return this.request("/bamboo/dashboard");
  }

  listBambooTasks(bucket: BambooTaskBucket): Promise<{
    bucket: BambooTaskBucket;
    tasks: BambooRecord[];
  }> {
    return this.request(`/bamboo/tasks?bucket=${encodeURIComponent(bucket)}`);
  }

  createBambooRecord(
    baseInfo: Record<string, unknown>,
    idempotencyKey: string,
  ): Promise<BambooRecord> {
    return this.request("/bamboo/records", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ base_info: baseInfo }),
    });
  }

  getBambooRecord(recordId: string): Promise<BambooRecord> {
    return this.request(`/bamboo/records/${encodeURIComponent(recordId)}`);
  }

  submitBambooStage(
    recordId: string,
    stage: BambooStage,
    input: SubmitBambooStageInput,
    idempotencyKey: string,
  ): Promise<BambooRecord> {
    return this.request(
      `/bamboo/records/${encodeURIComponent(recordId)}/stages/${encodeURIComponent(stage)}/submit`,
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify(input),
      },
    );
  }

  getBambooOperations(recordId: string): Promise<BambooOperationsSummary> {
    return this.request(`/bamboo/records/${encodeURIComponent(recordId)}/operations`);
  }

  createBambooInspection(
    recordId: string,
    input: Record<string, unknown>,
    idempotencyKey: string,
  ): Promise<BambooInspection> {
    return this.request(`/bamboo/records/${encodeURIComponent(recordId)}/inspections`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(input),
    });
  }

  uploadBambooEvidence(
    inspectionId: string,
    evidenceType: "PHOTO" | "AUDIO",
    file: File,
    idempotencyKey: string,
  ): Promise<BambooEvidence> {
    const body = new FormData();
    body.set("evidence_type", evidenceType);
    body.set("file", file);
    return this.request(`/bamboo/inspections/${encodeURIComponent(inspectionId)}/evidence`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body,
    });
  }

  closeBambooException(exceptionId: string, resolution: string): Promise<Record<string, unknown>> {
    return this.request(`/bamboo/inspection-exceptions/${encodeURIComponent(exceptionId)}/close`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ resolution }),
    });
  }

  returnBambooRecord(
    recordId: string,
    targetStages: BambooStage[],
    reason: string,
  ): Promise<Record<string, unknown>> {
    return this.request(`/bamboo/records/${encodeURIComponent(recordId)}/return`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ target_stages: targetStages, reason, source: "SUPERVISOR" }),
    });
  }

  requestBambooRoleChange(toRole: string, reason: string): Promise<BambooRoleChange> {
    return this.request("/bamboo/role-change-requests", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ to_role: toRole, reason }),
    });
  }

  listBambooRoleChanges(): Promise<BambooRoleChange[]> {
    return this.request("/bamboo/role-change-requests");
  }

  decideBambooRoleChange(requestId: string, approve: boolean, note: string): Promise<BambooRoleChange> {
    return this.request(`/bamboo/role-change-requests/${encodeURIComponent(requestId)}/decision`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ approve, note }),
    });
  }

  listBambooDailyBatches(): Promise<BambooDailyBatch[]> {
    return this.request("/bamboo/finance/daily-batches");
  }

  decideBambooFinanceItem(itemId: string, decision: string, note: string): Promise<BambooFinanceItem> {
    return this.request(`/bamboo/finance/items/${encodeURIComponent(itemId)}/decision`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ decision, note }),
    });
  }

  createBambooFinanceInquiry(itemId: string, subject: string, body: string): Promise<Record<string, unknown>> {
    return this.request(`/bamboo/finance/items/${encodeURIComponent(itemId)}/inquiries`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ subject, body }),
    });
  }

  listBambooFinanceInquiries(): Promise<Array<Record<string, unknown>>> {
    return this.request("/bamboo/finance/inquiries");
  }

  replyBambooFinanceInquiry(inquiryId: string, body: string, close = false): Promise<Record<string, unknown>> {
    return this.request(`/bamboo/finance/inquiries/${encodeURIComponent(inquiryId)}/reply`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ body, close }),
    });
  }

  createBambooPayrollRule(ruleKey: string, configuration: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request("/bamboo/payroll-rules", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ rule_key: ruleKey, configuration, system_default: false }),
    });
  }

  assignBambooEmployeeRole(employeeCode: string, roleCode: string): Promise<Record<string, unknown>> {
    return this.request("/bamboo/admin/assignments", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ employee_code: employeeCode, role_code: roleCode }),
    });
  }
}

export const mobileApiClient = new MobileApiClient();
