import { ApiRequestError } from "./review-workbench.js";

export interface TemplateArtifact {
  artifact_id: string;
  kind: string;
  download_name: string;
  sha256: string;
  download_url: string;
}

export interface TemplateVersion {
  version_id: string;
  template_key?: string;
  version?: number;
  status: string;
  fields: string[];
  artifacts: TemplateArtifact[];
}

export interface PreflightReport {
  ok: boolean;
  status: string;
  issues: Array<{ code: string; detail: string }>;
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class TemplateApi {
  constructor(
    private readonly baseUrl = "/api/v1",
    private readonly fetcher: Fetcher = fetch,
  ) {}

  createDraft(templateKey: string, pageSize: "A4" | "A5"): Promise<TemplateVersion> {
    return this.request("/templates", { template_key: templateKey, page_size: pageSize });
  }

  addField(versionId: string, field: {
    field_key: string; display_name: string; data_type: string; input_type: string;
    region: { x: number; y: number; width: number; height: number };
  }): Promise<TemplateVersion> {
    return this.request(`/template-versions/${encodeURIComponent(versionId)}/fields`, field);
  }

  preflight(versionId: string): Promise<PreflightReport> {
    return this.request(`/template-versions/${encodeURIComponent(versionId)}/preflight`);
  }

  publish(versionId: string): Promise<TemplateVersion> {
    return this.request(`/template-versions/${encodeURIComponent(versionId)}/publish`);
  }

  private async request<T>(path: string, body?: unknown): Promise<T> {
    const fetcher = this.fetcher;
    const response = await fetcher(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const problem = await response.json().catch(() => ({})) as { code?: string; detail?: string };
      throw new ApiRequestError(response.status, problem.code ?? "REQUEST_FAILED", problem.detail ?? "请求失败");
    }
    return response.json() as Promise<T>;
  }
}
