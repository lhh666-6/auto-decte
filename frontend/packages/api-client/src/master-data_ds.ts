import { ApiRequestError } from "./review-workbench.js";

export type MasterDataCatalog = "employees" | "work-orders" | "products" | "processes";

export interface MasterDataRecord {
  catalog: MasterDataCatalog;
  code: string;
  display_name: string;
  attributes: Record<string, unknown>;
  active: boolean;
  revision: number;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string;
}

export interface MasterDataAudit {
  audit_id: string;
  catalog: MasterDataCatalog;
  code: string;
  revision: number;
  event_type: "CREATE" | "UPDATE" | "DEACTIVATE" | "REACTIVATE";
  actor_id: string;
  timestamp: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string;
}

export interface CreateMasterDataInput {
  code: string;
  display_name: string;
  attributes: Record<string, unknown>;
  reason: string;
}

export interface UpdateMasterDataInput {
  expected_revision: number;
  display_name?: string;
  attributes?: Record<string, unknown>;
  reason: string;
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class MasterDataApi {
  constructor(
    private readonly baseUrl = "/api/v1",
    private readonly fetcher: Fetcher = fetch,
  ) {}

  async list(
    catalog: MasterDataCatalog,
    options: { includeInactive?: boolean; query?: string } = {},
  ): Promise<MasterDataRecord[]> {
    const search = new URLSearchParams();
    if (options.includeInactive) search.set("include_inactive", "true");
    if (options.query?.trim()) search.set("query", options.query.trim());
    const suffix = search.size ? `?${search.toString()}` : "";
    const response = await this.request<{ items: MasterDataRecord[] }>(
      `/master-data/${catalog}${suffix}`,
    );
    return response.items;
  }

  get(catalog: MasterDataCatalog, code: string): Promise<MasterDataRecord> {
    return this.request(
      `/master-data/${catalog}/${encodeURIComponent(code)}`,
    );
  }

  create(
    catalog: MasterDataCatalog,
    input: CreateMasterDataInput,
  ): Promise<MasterDataRecord> {
    return this.request(`/master-data/${catalog}`, { method: "POST", body: input });
  }

  update(
    catalog: MasterDataCatalog,
    code: string,
    input: UpdateMasterDataInput,
  ): Promise<MasterDataRecord> {
    return this.request(`/master-data/${catalog}/${encodeURIComponent(code)}`, {
      method: "PATCH",
      headers: { "If-Match": `"${input.expected_revision}"` },
      body: input,
    });
  }

  setActive(
    catalog: MasterDataCatalog,
    code: string,
    active: boolean,
    expectedRevision: number,
    reason: string,
  ): Promise<MasterDataRecord> {
    return this.request(
      `/master-data/${catalog}/${encodeURIComponent(code)}/${active ? "reactivate" : "deactivate"}`,
      {
        method: "POST",
        headers: { "If-Match": `"${expectedRevision}"` },
        body: { expected_revision: expectedRevision, reason },
      },
    );
  }

  audits(catalog: MasterDataCatalog, code: string): Promise<MasterDataAudit[]> {
    return this.request(
      `/master-data/${catalog}/${encodeURIComponent(code)}/audit`,
    );
  }

  private async request<T>(
    path: string,
    options: { method?: string; headers?: Record<string, string>; body?: unknown } = {},
  ): Promise<T> {
    const headers = { ...options.headers };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    const fetcher = this.fetcher;
    const response = await fetcher(`${this.baseUrl}${path}`, {
      method: options.method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    if (!response.ok) {
      const problem = await response.json().catch(() => ({})) as {
        code?: string;
        detail?: string;
      };
      throw new ApiRequestError(
        response.status,
        problem.code ?? "REQUEST_FAILED",
        problem.detail ?? `Request failed with status ${response.status}`,
      );
    }
    return response.json() as Promise<T>;
  }
}
