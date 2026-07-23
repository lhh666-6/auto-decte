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
export type BambooFormType = "SORTING" | "DIPPING_DRYING";
export type BambooTaskBucket = "available" | "waiting" | "completed";

export interface BambooSourceSnapshot {
  record_id?: string;
  display_no?: string;
  revision?: number;
  base_info?: Record<string, unknown>;
  source_status?: "CURRENT" | "UPSTREAM_CHANGED";
  latest_revision?: number;
  original_revision?: number;
  changed_at?: string;
  [key: string]: unknown;
}

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

export interface BambooUpstreamRecord {
  record_id: string;
  display_no: string;
  factory_id: string;
  form_type: BambooFormType;
  base_info: Record<string, unknown>;
  current_stage: BambooStage | null;
  status: "ACTIVE" | "COMPLETED";
  revision: number;
  submissions: BambooStageSubmission[];
}

export interface BambooRecord {
  record_id: string;
  display_no: string;
  factory_id: string;
  source_type: string;
  source_ref: string | null;
  form_type: BambooFormType;
  production_object_id: string | null;
  source_record_id: string | null;
  source_snapshot: BambooSourceSnapshot;
  base_info: Record<string, unknown>;
  current_stage: BambooStage | null;
  status: "ACTIVE" | "COMPLETED";
  revision: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  submissions: BambooStageSubmission[];
  upstream_record: BambooUpstreamRecord | null;
}

export interface BambooDashboard {
  available: number;
  waiting: number;
  completed: number;
}

export interface BambooRecordPresetOptions {
  options_version: string;
  special_classes: string[];
  lengths: string[];
  shades: string[];
  grades: string[];
  weight_factors: Record<string, string>;
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

export interface BambooInspectionWindow {
  record_id: string;
  display_no: string;
  form_type: "SORTING" | "DIPPING_DRYING";
  cage_no: string;
  status: string;
  opened_at: string;
  deadline_at: string;
  inside_window: boolean;
  claimed_by: string | null;
  claimed_at: string | null;
  completed_at: string | null;
  appeal_deadline_at: string | null;
  appeal_claimed_by: string | null;
  appeal_submitted_at: string | null;
  appeal_decision: string | null;
  revision: number;
}

export interface BambooNotification {
  notification_id: string;
  category: string;
  title: string;
  body: string;
  link: string | null;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface SubmitBambooInspectionInput {
  conclusion: "CONFORMING" | "NONCONFORMING";
  targetStage?: BambooStage;
  textEvidence?: string;
  photos?: File[];
  audio?: File | null;
  deviceId: string;
}

export interface BambooRoleOption {
  role_code: string;
  display_name: string;
  category: string;
  self_requestable: boolean;
}

export interface BambooFactoryEmployee {
  employee_code: string;
  employee_name: string;
  factory_id: string;
  role_code: string;
  role_name: string;
}

export interface BambooFactory {
  factory_id: string;
  code: string;
  name: string;
}

export interface BambooPersonnelTransfer {
  transfer_id: string;
  employee_code: string;
  transfer_type: "INTERNAL" | "CROSS_FACTORY" | "MANAGER_REPLACEMENT";
  source_factory_id: string;
  target_factory_id: string;
  from_role: string;
  to_role: string;
  reason: string;
  status: string;
  source_manager_decision: string | null;
  target_manager_decision: string | null;
  admin_decision: string | null;
  executed_at: string | null;
  revision: number;
}

export interface BambooHistoryItem {
  activity_id: string;
  record_id: string;
  display_no: string;
  form_type: string;
  cage_no: string;
  action: string;
  submitted_at: string;
  current_stage: BambooStage | null;
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

function createMobileClientId(prefix = "mobile"): string {
  const randomUuid = globalThis.crypto?.randomUUID?.();
  if (randomUuid) return randomUuid;
  const randomPart = Math.random().toString(36).slice(2, 12);
  return `${prefix}-${Date.now().toString(36)}-${randomPart}`;
}

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

  listBambooTasks(bucket: BambooTaskBucket, cageNo = ""): Promise<{
    bucket: BambooTaskBucket;
    tasks: BambooRecord[];
  }> {
    const params = new URLSearchParams({ bucket });
    if (cageNo.trim()) params.set("cage_no", cageNo.trim());
    return this.request(`/bamboo/tasks?${params.toString()}`);
  }

  getBambooRecordOptions(): Promise<BambooRecordPresetOptions> {
    return this.request("/bamboo/record-options");
  }

  createBambooRecord(
    baseInfo: Record<string, unknown>,
    idempotencyKey: string,
  ): Promise<BambooRecord> {
    return this.request("/bamboo/records", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ form_type: "SORTING", base_info: baseInfo }),
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
      headers: { "Idempotency-Key": createMobileClientId("inspection-exception") },
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
      headers: { "Idempotency-Key": createMobileClientId("bamboo-return") },
      body: JSON.stringify({ target_stages: targetStages, reason, source: "SUPERVISOR" }),
    });
  }

  requestBambooRoleChange(toRole: string, reason: string): Promise<BambooRoleChange> {
    return this.request("/bamboo/role-change-requests", {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("role-change") },
      body: JSON.stringify({ to_role: toRole, reason }),
    });
  }

  listBambooRoleChanges(): Promise<BambooRoleChange[]> {
    return this.request("/bamboo/role-change-requests");
  }

  decideBambooRoleChange(requestId: string, approve: boolean, note: string): Promise<BambooRoleChange> {
    return this.request(`/bamboo/role-change-requests/${encodeURIComponent(requestId)}/decision`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("role-change-decision") },
      body: JSON.stringify({ approve, note }),
    });
  }

  listBambooDailyBatches(): Promise<BambooDailyBatch[]> {
    return this.request("/bamboo/finance/daily-batches");
  }

  decideBambooFinanceItem(itemId: string, decision: string, note: string): Promise<BambooFinanceItem> {
    return this.request(`/bamboo/finance/items/${encodeURIComponent(itemId)}/decision`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("finance-decision") },
      body: JSON.stringify({ decision, note }),
    });
  }

  createBambooFinanceInquiry(itemId: string, subject: string, body: string): Promise<Record<string, unknown>> {
    return this.request(`/bamboo/finance/items/${encodeURIComponent(itemId)}/inquiries`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("finance-inquiry") },
      body: JSON.stringify({ subject, body }),
    });
  }

  listBambooFinanceInquiries(): Promise<Array<Record<string, unknown>>> {
    return this.request("/bamboo/finance/inquiries");
  }

  replyBambooFinanceInquiry(inquiryId: string, body: string, close = false): Promise<Record<string, unknown>> {
    return this.request(`/bamboo/finance/inquiries/${encodeURIComponent(inquiryId)}/reply`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("finance-reply") },
      body: JSON.stringify({ body, close }),
    });
  }

  createBambooPayrollRule(ruleKey: string, configuration: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request("/bamboo/payroll-rules", {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("payroll-rule") },
      body: JSON.stringify({ rule_key: ruleKey, configuration, system_default: false }),
    });
  }

  assignBambooEmployeeRole(employeeCode: string, roleCode: string): Promise<Record<string, unknown>> {
    return this.request("/bamboo/admin/assignments", {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("employee-role") },
      body: JSON.stringify({ employee_code: employeeCode, role_code: roleCode }),
    });
  }

  listBambooInspectionQueue(bucket: "active" | "history" = "active", query = ""): Promise<{
    bucket: string;
    items: BambooInspectionWindow[];
  }> {
    const params = new URLSearchParams({ bucket });
    if (query.trim()) params.set("q", query.trim());
    return this.request(`/bamboo/inspection-queue?${params.toString()}`);
  }

  claimBambooInspection(recordId: string, idempotencyKey: string): Promise<BambooInspectionWindow> {
    return this.request(`/bamboo/inspection-queue/${encodeURIComponent(recordId)}/claim`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
    });
  }

  submitBambooInspection(
    recordId: string,
    input: SubmitBambooInspectionInput,
    idempotencyKey: string,
  ): Promise<BambooInspection> {
    const body = new FormData();
    body.set("conclusion", input.conclusion);
    body.set("device_id", input.deviceId);
    if (input.targetStage) body.set("target_stage", input.targetStage);
    if (input.textEvidence) body.set("text_evidence", input.textEvidence);
    for (const photo of input.photos ?? []) body.append("photos", photo);
    if (input.audio) body.set("audio", input.audio);
    return this.request(`/bamboo/records/${encodeURIComponent(recordId)}/inspection-submit`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body,
    });
  }

  terminateBambooInspection(recordId: string): Promise<BambooInspectionWindow> {
    return this.request(`/bamboo/inspection-queue/${encodeURIComponent(recordId)}/terminate`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("inspection-terminate") },
      body: JSON.stringify({ confirm: true }),
    });
  }

  claimBambooInspectionAppeal(recordId: string): Promise<BambooInspectionWindow> {
    return this.request(`/bamboo/inspection-queue/${encodeURIComponent(recordId)}/appeal/claim`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("appeal-claim") },
    });
  }

  submitBambooInspectionAppeal(
    recordId: string,
    targetStage: BambooStage,
    textEvidence: string,
  ): Promise<BambooInspectionWindow> {
    return this.request(`/bamboo/inspection-queue/${encodeURIComponent(recordId)}/appeal`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("appeal-submit") },
      body: JSON.stringify({ target_stage: targetStage, text_evidence: textEvidence }),
    });
  }

  decideBambooInspectionAppeal(
    recordId: string,
    approve: boolean,
    note: string,
  ): Promise<BambooInspectionWindow> {
    return this.request(`/bamboo/inspection-queue/${encodeURIComponent(recordId)}/appeal/decision`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("appeal-decision") },
      body: JSON.stringify({ approve, note }),
    });
  }

  listBambooNotifications(): Promise<{ items: BambooNotification[] }> {
    return this.request("/bamboo/notifications");
  }

  readBambooNotification(notificationId: string): Promise<BambooNotification> {
    return this.request(`/bamboo/notifications/${encodeURIComponent(notificationId)}/read`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("notification-read") },
    });
  }

  listBambooRoleOptions(): Promise<BambooRoleOption[]> {
    return this.request("/bamboo/role-options");
  }

  listBambooFactoryEmployees(): Promise<BambooFactoryEmployee[]> {
    return this.request("/bamboo/admin/employees");
  }

  listBambooFactories(): Promise<BambooFactory[]> {
    return this.request("/bamboo/factories");
  }

  listBambooPersonnelTransfers(): Promise<BambooPersonnelTransfer[]> {
    return this.request("/bamboo/personnel-transfers");
  }

  createBambooPersonnelTransfer(input: {
    employee_code: string;
    to_role: string;
    target_factory_id: string;
    reason: string;
  }): Promise<BambooPersonnelTransfer> {
    return this.request("/bamboo/personnel-transfers", {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("personnel-transfer") },
      body: JSON.stringify(input),
    });
  }

  decideBambooPersonnelTransferAsManager(
    transferId: string,
    approve: boolean,
    note: string,
  ): Promise<BambooPersonnelTransfer> {
    return this.request(`/bamboo/personnel-transfers/${encodeURIComponent(transferId)}/manager-decision`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("transfer-manager-decision") },
      body: JSON.stringify({ approve, note }),
    });
  }

  executeBambooPersonnelTransfer(
    transferId: string,
    approve: boolean,
    note: string,
  ): Promise<BambooPersonnelTransfer> {
    return this.request(`/bamboo/personnel-transfers/${encodeURIComponent(transferId)}/execute`, {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("transfer-admin-execute") },
      body: JSON.stringify({ approve, note }),
    });
  }

  createBambooFactoryEmployee(
    employeeName: string,
    initialPin: string,
    roleCode: string,
  ): Promise<BambooFactoryEmployee> {
    return this.request("/bamboo/admin/employees", {
      method: "POST",
      headers: { "Idempotency-Key": createMobileClientId("factory-employee") },
      body: JSON.stringify({
        employee_name: employeeName,
        initial_pin: initialPin,
        role_code: roleCode,
      }),
    });
  }

  listBambooHistory(): Promise<BambooHistoryItem[]> {
    return this.request("/bamboo/history");
  }
}

export const mobileApiClient = new MobileApiClient();
