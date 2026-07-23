import type {
  BusinessTask,
  FinanceRecord,
  GovernedExportBatch,
  ManagedFormVersion,
  ManagedFormField,
  ManagementNotification,
  ProposedBusinessRule,
  PayrollBatch,
  PayrollResult,
  PayrollRuleVersion,
  ReportMappingVersion,
  ReportTemplateVersion,
  SubmissionCorrection,
  WorkflowVersion,
  WebSession,
  WorkspaceOverview,
} from "./types";

export interface WebProblem {
  title: string;
  status: number;
  code: string;
  detail: string;
  request_id: string;
  failures?: unknown;
}

export class WebApiError extends Error {
  constructor(public readonly problem: WebProblem) {
    super(problem.detail);
    this.name = "WebApiError";
  }

  get status() {
    return this.problem.status;
  }
}

export type WebFetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

const WEB_BASE = "/api/v1/web";

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  const item = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
}

async function readProblem(response: Response): Promise<WebProblem> {
  const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  const nested = typeof body.detail === "object" && body.detail
    ? body.detail as Record<string, unknown>
    : body;
  const detail = typeof nested.detail === "string"
    ? nested.detail
    : typeof body.detail === "string"
      ? body.detail
      : response.statusText || "请求失败";
  return {
    title: typeof body.title === "string" ? body.title : "请求失败",
    status: response.status,
    code: typeof nested.code === "string" ? nested.code : `HTTP_${response.status}`,
    detail,
    request_id: typeof body.request_id === "string" ? body.request_id : "",
    failures: nested.failures,
  };
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  fetcher: WebFetcher = fetch,
): Promise<T> {
  const response = await fetcher(path, {
    ...init,
    credentials: "include",
  });
  if (!response.ok) throw new WebApiError(await readProblem(response));
  return response.json() as Promise<T>;
}

export function getSession(fetcher?: WebFetcher) {
  return request<WebSession>(`${WEB_BASE}/auth/session`, {}, fetcher);
}

export function login(
  employeeCode: string,
  pin: string,
  fetcher?: WebFetcher,
) {
  return request<WebSession>(
    `${WEB_BASE}/auth/login`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ employee_code: employeeCode, pin }),
    },
    fetcher,
  );
}

export async function logoutWebSession(fetcher: WebFetcher = fetch) {
  const csrfToken = readCookie("web_csrf");
  const headers: Record<string, string> = {};
  if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const response = await fetcher(`${WEB_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers,
  });
  if (!response.ok) throw new WebApiError(await readProblem(response));
}

export function getOverview(segment: string, fetcher?: WebFetcher) {
  return request<WorkspaceOverview>(
    `/api/v1/${segment}/overview`,
    {},
    fetcher,
  );
}

function csrfHeaders(json = false): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = readCookie("web_csrf");
  if (token) headers["X-CSRF-Token"] = token;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

export async function listManagedForms(
  workspace: "finance" | "plant",
  fetcher?: WebFetcher,
) {
  return request<{ items: ManagedFormVersion[] }>(
    workspace === "finance"
      ? "/api/v1/finance/form-definitions"
      : "/api/v1/plant/forms",
    {},
    fetcher,
  );
}

export function createManagedForm(
  body: {
    form_key: string;
    name: string;
    owner_role: string;
    schema_json: { fields: ManagedFormField[] };
  },
  fetcher?: WebFetcher,
) {
  return request<ManagedFormVersion>(
    "/api/v1/finance/form-definitions",
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify(body),
    },
    fetcher,
  );
}

export function submitManagedFormApproval(
  versionId: string,
  fetcher?: WebFetcher,
) {
  return request<ManagedFormVersion>(
    `/api/v1/finance/form-versions/${versionId}/submit-approval`,
    { method: "POST", headers: csrfHeaders() },
    fetcher,
  );
}

export function updateManagedForm(
  versionId: string,
  expectedRevision: number,
  schemaJson: { fields: ManagedFormField[] },
  fetcher?: WebFetcher,
) {
  return request<ManagedFormVersion>(
    `/api/v1/finance/form-versions/${versionId}`,
    {
      method: "PATCH",
      headers: csrfHeaders(true),
      body: JSON.stringify({
        expected_revision: expectedRevision,
        schema_json: schemaJson,
      }),
    },
    fetcher,
  );
}

export function listManagedFormApprovals(fetcher?: WebFetcher) {
  return request<{ items: ManagedFormVersion[] }>(
    "/api/v1/admin/form-approvals",
    {},
    fetcher,
  );
}

export function decideManagedFormApproval(
  versionId: string,
  decision: "APPROVE" | "REJECT",
  fetcher?: WebFetcher,
) {
  return request<ManagedFormVersion>(
    `/api/v1/admin/form-approvals/${versionId}/decision`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ decision }),
    },
    fetcher,
  );
}

export function activateManagedForm(
  versionId: string,
  plantIds: string[],
  fetcher?: WebFetcher,
) {
  return request<{ version_id: string; status: string; plant_ids: string[] }>(
    `/api/v1/admin/form-versions/${versionId}/activate`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ plant_ids: plantIds }),
    },
    fetcher,
  );
}

export function listPlantNotifications(fetcher?: WebFetcher) {
  return request<{ items: ManagementNotification[] }>(
    "/api/v1/plant/notifications",
    {},
    fetcher,
  );
}

export function acknowledgePlantNotification(
  notificationId: string,
  fetcher?: WebFetcher,
) {
  return request<ManagementNotification>(
    `/api/v1/plant/notifications/${notificationId}/acknowledge`,
    { method: "POST", headers: csrfHeaders() },
    fetcher,
  );
}

export function createDiscoverySession(title: string, fetcher?: WebFetcher) {
  return request<{ session_id: string }>(
    "/api/v1/finance/business-discovery/sessions",
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ title, source_refs: [] }),
    },
    fetcher,
  );
}

export function sendDiscoveryMessage(
  sessionId: string,
  content: string,
  fetcher?: WebFetcher,
) {
  return request<{
    proposed_rules: ProposedBusinessRule[];
    assistant_message: string;
  }>(
    `/api/v1/finance/business-discovery/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ content }),
    },
    fetcher,
  );
}

export function confirmDiscoveryRules(
  sessionId: string,
  ruleIds: string[],
  fetcher?: WebFetcher,
) {
  return request<{ baseline: { version: number; status: string } }>(
    `/api/v1/finance/business-discovery/sessions/${sessionId}/confirm`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ rule_ids: ruleIds, note: "财务页面确认" }),
    },
    fetcher,
  );
}

export function createWorkflow(
  body: {
    workflow_key: string;
    name: string;
    graph_json: WorkflowVersion["graph_json"];
    canvas_json: Record<string, unknown>;
  },
  fetcher?: WebFetcher,
) {
  return request<WorkflowVersion>(
    "/api/v1/finance/workflows",
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify(body),
    },
    fetcher,
  );
}

export function validateWorkflow(versionId: string, fetcher?: WebFetcher) {
  return request<{
    valid: boolean;
    errors: Array<{ code: string; detail: string; node_id: string }>;
  }>(
    `/api/v1/finance/workflow-versions/${versionId}/validate`,
    { method: "POST", headers: csrfHeaders() },
    fetcher,
  );
}

export function listWorkflowApprovals(fetcher?: WebFetcher) {
  return request<{ items: WorkflowVersion[] }>(
    "/api/v1/admin/workflow-approvals",
    {},
    fetcher,
  );
}

export function decideWorkflow(
  versionId: string,
  decision: "APPROVE" | "REJECT",
  fetcher?: WebFetcher,
) {
  return request<WorkflowVersion>(
    `/api/v1/admin/workflow-approvals/${versionId}/decision`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ decision }),
    },
    fetcher,
  );
}

export function activateWorkflow(
  versionId: string,
  plantIds: string[],
  fetcher?: WebFetcher,
) {
  return request<{ status: string }>(
    `/api/v1/admin/workflow-versions/${versionId}/activate`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ plant_ids: plantIds }),
    },
    fetcher,
  );
}

export function listPlantWorkflows(fetcher?: WebFetcher) {
  return request<{ items: WorkflowVersion[] }>(
    "/api/v1/plant/workflows",
    {},
    fetcher,
  );
}

export function getFinanceLedgerOverview(fetcher?: WebFetcher) {
  return request<{ today: number; month: number; year: number }>(
    "/api/v1/finance/ledger/overview", {}, fetcher,
  );
}

export function listFinanceLedger(fetcher?: WebFetcher) {
  return request<{ items: FinanceRecord[] }>("/api/v1/finance/ledger", {}, fetcher);
}

export function listFinanceCorrections(fetcher?: WebFetcher) {
  return request<{ items: SubmissionCorrection[] }>(
    "/api/v1/finance/corrections", {}, fetcher,
  );
}

export function listFinanceTasks(fetcher?: WebFetcher) {
  return request<{ items: BusinessTask[] }>(
    "/api/v1/finance/business-tasks", {}, fetcher,
  );
}

export function attachCorrectionReplacement(
  correctionId: string,
  body: {
    replacement_submission_id: string;
    actual_actor_id: string;
    delegate_reason: string;
  },
  fetcher?: WebFetcher,
) {
  return request<{ correction_id: string; status: string }>(
    `/api/v1/finance/corrections/${correctionId}/replacement`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify(body),
    },
    fetcher,
  );
}

export function reviewCorrection(
  correctionId: string,
  approved: boolean,
  note: string,
  fetcher?: WebFetcher,
) {
  return request<{ correction_id: string; status: string }>(
    `/api/v1/finance/corrections/${correctionId}/review`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ approved, note }),
    },
    fetcher,
  );
}

export function getPlantProduction(fetcher?: WebFetcher) {
  return request<{
    overview: { today: number; month: number; year: number };
    records: FinanceRecord[];
  }>("/api/v1/plant/production", {}, fetcher);
}

export function getPlantExceptions(fetcher?: WebFetcher) {
  return request<{
    corrections: SubmissionCorrection[];
    tasks: BusinessTask[];
  }>("/api/v1/plant/exceptions", {}, fetcher);
}

export function returnPlantSubmission(
  submissionId: string,
  reason: string,
  assignedTo: string,
  fetcher?: WebFetcher,
) {
  return request<{ correction_id: string; task_id: string; status: string }>(
    `/api/v1/plant/submissions/${submissionId}/return`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ reason, assigned_to: assignedTo }),
    },
    fetcher,
  );
}

export function listPayrollRules(fetcher?: WebFetcher) {
  return request<{ items: PayrollRuleVersion[] }>(
    "/api/v1/finance/payroll-rules", {}, fetcher,
  );
}

export function createPayrollRule(
  body: {
    rule_key: string;
    name: string;
    factory_id: string;
    position: string;
    dsl: { metric: string; rate: string; base: string };
  },
  fetcher?: WebFetcher,
) {
  return request<PayrollRuleVersion>(
    "/api/v1/finance/payroll-rules",
    { method: "POST", headers: csrfHeaders(true), body: JSON.stringify(body) },
    fetcher,
  );
}

export function submitPayrollRule(versionId: string, fetcher?: WebFetcher) {
  return request<PayrollRuleVersion>(
    `/api/v1/finance/payroll-rules/${versionId}/submit-approval`,
    { method: "POST", headers: csrfHeaders() },
    fetcher,
  );
}

export function listPayrollApprovals(fetcher?: WebFetcher) {
  return request<{ items: PayrollRuleVersion[] }>(
    "/api/v1/admin/payroll-approvals", {}, fetcher,
  );
}

export function decidePayrollRule(
  versionId: string,
  approved: boolean,
  fetcher?: WebFetcher,
) {
  return request<PayrollRuleVersion>(
    `/api/v1/admin/payroll-approvals/${versionId}/decision`,
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({ approved, note: approved ? "管理员批准" : "管理员退回" }),
    },
    fetcher,
  );
}

export function calculatePayroll(
  ruleVersionId: string,
  periodStart: string,
  periodEnd: string,
  fetcher?: WebFetcher,
) {
  return request<PayrollBatch>(
    "/api/v1/finance/payroll-calculations",
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({
        rule_version_id: ruleVersionId,
        period_start: periodStart,
        period_end: periodEnd,
      }),
    },
    fetcher,
  );
}

export function listPayrollBatches(fetcher?: WebFetcher) {
  return request<{ items: PayrollBatch[] }>(
    "/api/v1/finance/payroll-calculations", {}, fetcher,
  );
}

export function confirmPayrollBatch(batchId: string, fetcher?: WebFetcher) {
  return request<PayrollBatch>(
    `/api/v1/finance/payroll-calculations/${batchId}/confirm`,
    { method: "POST", headers: csrfHeaders() },
    fetcher,
  );
}

export function listOfficialPayroll(
  workspace: "finance" | "admin" | "plant",
  fetcher?: WebFetcher,
) {
  return request<{ items: PayrollResult[] }>(
    `/api/v1/${workspace}/payroll`, {}, fetcher,
  );
}

export async function uploadReportTemplate(file: File, fetcher: WebFetcher = fetch) {
  const response = await fetcher("/api/v1/admin/report-templates", {
    method: "POST",
    credentials: "include",
    headers: {
      ...csrfHeaders(),
      "Content-Type": file.type || "application/octet-stream",
      "X-Filename": encodeURIComponent(file.name),
    },
    body: file,
  });
  if (!response.ok) throw new WebApiError(await readProblem(response));
  return response.json() as Promise<ReportTemplateVersion>;
}

export function listReportTemplates(fetcher?: WebFetcher) {
  return request<{ items: ReportTemplateVersion[] }>(
    "/api/v1/finance/report-templates", {}, fetcher,
  );
}

export function listReportMappings(fetcher?: WebFetcher) {
  return request<{ items: ReportMappingVersion[] }>(
    "/api/v1/finance/report-mappings", {}, fetcher,
  );
}

export function createReportMapping(
  templateVersionId: string,
  mappingJson: ReportMappingVersion["mapping_json"],
  fetcher?: WebFetcher,
) {
  return request<ReportMappingVersion>(
    "/api/v1/finance/report-mappings",
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({
        template_version_id: templateVersionId,
        mapping_json: mappingJson,
      }),
    },
    fetcher,
  );
}

export function confirmReportMapping(mappingVersionId: string, fetcher?: WebFetcher) {
  return request<ReportMappingVersion>(
    `/api/v1/finance/report-mappings/${mappingVersionId}/confirm`,
    { method: "POST", headers: csrfHeaders() },
    fetcher,
  );
}

export function createGovernedExport(
  templateVersionId: string,
  mappingVersionId: string,
  factoryId: string,
  fetcher?: WebFetcher,
) {
  return request<GovernedExportBatch>(
    "/api/v1/finance/exports",
    {
      method: "POST",
      headers: csrfHeaders(true),
      body: JSON.stringify({
        template_version_id: templateVersionId,
        mapping_version_id: mappingVersionId,
        filters: factoryId ? { factory_id: factoryId } : {},
        idempotency_key: crypto.randomUUID(),
      }),
    },
    fetcher,
  );
}

export function listGovernedExports(fetcher?: WebFetcher) {
  return request<{ items: GovernedExportBatch[] }>(
    "/api/v1/finance/exports", {}, fetcher,
  );
}
