import type { WebSession, WorkspaceOverview } from "./types";

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
