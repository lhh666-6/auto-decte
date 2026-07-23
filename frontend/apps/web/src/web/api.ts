import type {
  ManagedFormVersion,
  ManagedFormField,
  ManagementNotification,
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
