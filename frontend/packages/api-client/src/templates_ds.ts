import { ApiRequestError } from "./review-workbench.js";

export interface TemplateArtifact {
  artifact_id: string;
  kind: string;
  download_name: string;
  sha256: string;
  download_url: string;
}

export interface TemplateRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TemplateFieldRules {
  required: boolean;
  minimum_value: number | null;
  maximum_value: number | null;
  allowed_values: string[];
  master_data_source: string | null;
  allow_exception_reason: boolean;
}

export interface TemplateExportTarget {
  workbook: string;
  worksheet: string;
  business_column: string;
}

export interface TemplateField {
  field_key: string;
  display_name: string;
  data_type: string;
  input_type: string;
  recognition_engine: string;
  minimum_prefill_confidence: number;
  rules: TemplateFieldRules;
  export_target: TemplateExportTarget;
  region: TemplateRect;
}

export interface TemplatePage {
  size: string;
  orientation: string;
  width_mm: number;
  height_mm: number;
  canonical_dpi: number;
  canonical_width_px: number;
  canonical_height_px: number;
}

export interface TemplateVersion {
  version_id: string;
  template_key: string;
  display_name: string;
  description: string;
  version: number;
  status: TemplateStatus;
  parent_version_id: string | null;
  page: TemplatePage;
  fields: TemplateField[];
  artifacts: TemplateArtifact[];
}

export type TemplateStatus =
  | "DRAFT"
  | "PREFLIGHT_FAILED"
  | "READY_TO_PUBLISH"
  | "PUBLISHED"
  | "DEPRECATED"
  | "RETIRED";

export type EditableTemplateStatus = "DRAFT" | "PREFLIGHT_FAILED" | "READY_TO_PUBLISH";

export interface TemplateDraftSummary {
  version_id: string;
  version: number;
  status: EditableTemplateStatus;
  field_count: number;
}

export function isEditableTemplateStatus(status: string): status is EditableTemplateStatus {
  return status === "DRAFT" || status === "PREFLIGHT_FAILED" || status === "READY_TO_PUBLISH";
}

export interface TemplateLibraryItem {
  template_key: string;
  display_name: string;
  description: string;
  version_id: string;
  current_published_version: number | null;
  version: number;
  status: TemplateStatus;
  page: TemplatePage;
  field_count: number;
  active_draft: TemplateDraftSummary | null;
}

export type TemplateFieldInput = TemplateField;

export interface PreflightReport {
  ok: boolean;
  status: TemplateStatus;
  issues: Array<{ code: string; detail: string }>;
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
type RequestOptions = {
  method: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
};

export class TemplateApi {
  constructor(
    private readonly baseUrl = "/api/v1",
    private readonly fetcher: Fetcher = fetch,
  ) {}

  createDraft(
    templateKey: string,
    pageSize: "A4" | "A5",
    displayName: string,
    description: string,
  ): Promise<TemplateVersion> {
    return this.request("/templates", {
      method: "POST",
      body: {
        template_key: templateKey,
        page_size: pageSize,
        display_name: displayName,
        description,
      },
    });
  }

  listTemplates(): Promise<TemplateLibraryItem[]> {
    return this.request("/templates", { method: "GET" });
  }

  getVersion(versionId: string): Promise<TemplateVersion> {
    return this.request(`/template-versions/${encodeURIComponent(versionId)}`, { method: "GET" });
  }

  clone(versionId: string): Promise<TemplateVersion> {
    return this.request(`/template-versions/${encodeURIComponent(versionId)}/clone`, { method: "POST" });
  }

  updateMetadata(
    templateKey: string,
    displayName: string,
    description: string,
  ): Promise<{ template_key: string; display_name: string; description: string }> {
    return this.request(`/templates/${encodeURIComponent(templateKey)}`, {
      method: "PATCH",
      body: { display_name: displayName, description },
    });
  }

  discardDraft(versionId: string): Promise<void> {
    return this.request(`/template-versions/${encodeURIComponent(versionId)}`, {
      method: "DELETE",
    });
  }

  retireTemplate(templateKey: string): Promise<void> {
    return this.request(`/templates/${encodeURIComponent(templateKey)}/retire`, {
      method: "POST",
    });
  }

  addField(versionId: string, field: TemplateFieldInput): Promise<TemplateVersion> {
    return this.request(`/template-versions/${encodeURIComponent(versionId)}/fields`, { method: "POST", body: field });
  }

  replaceField(versionId: string, fieldKey: string, field: TemplateFieldInput): Promise<TemplateVersion> {
    return this.request(
      `/template-versions/${encodeURIComponent(versionId)}/fields/${encodeURIComponent(fieldKey)}`,
      { method: "PATCH", body: field },
    );
  }

  deleteField(versionId: string, fieldKey: string): Promise<TemplateVersion> {
    return this.request(
      `/template-versions/${encodeURIComponent(versionId)}/fields/${encodeURIComponent(fieldKey)}`,
      { method: "DELETE" },
    );
  }

  preflight(versionId: string): Promise<PreflightReport> {
    return this.request(`/template-versions/${encodeURIComponent(versionId)}/preflight`, { method: "POST" });
  }

  publish(versionId: string): Promise<TemplateVersion> {
    return this.request(`/template-versions/${encodeURIComponent(versionId)}/publish`, { method: "POST" });
  }

  private async request<T>(path: string, options: RequestOptions): Promise<T> {
    const headers: Record<string, string> = options.body === undefined ? {} : { "Content-Type": "application/json" };
    const fetcher = this.fetcher;
    const response = await fetcher(`${this.baseUrl}${path}`, {
      method: options.method,
      headers,
      ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
    });
    if (response.status === 204) {
      return undefined as T;
    }
    if (!response.ok) {
      const problem = await response.json().catch(() => ({})) as { code?: string; detail?: string };
      throw new ApiRequestError(
        response.status,
        problem.code ?? "REQUEST_FAILED",
        problem.detail ?? `Request failed with status ${response.status}`,
      );
    }
    return response.json() as Promise<T>;
  }
}
