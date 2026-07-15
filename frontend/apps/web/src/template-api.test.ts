import { describe, expect, expectTypeOf, it, vi } from "vitest";

import { isEditableTemplateStatus } from "@form-detection/api-client";
import type {
  TemplateField,
  TemplateFieldInput,
  TemplateLibraryItem,
  TemplatePage,
  TemplateRect,
} from "@form-detection/api-client";
import { TemplateApi } from "../../../packages/api-client/src/templates_ds";

describe("TemplateApi", () => {
  it("re-exports the template contracts from the package entry point", () => {
    expectTypeOf<TemplateField>().toEqualTypeOf<TemplateField>();
    expectTypeOf<TemplateFieldInput>().toEqualTypeOf<TemplateFieldInput>();
    expectTypeOf<TemplateLibraryItem>().toEqualTypeOf<TemplateLibraryItem>();
    expectTypeOf<TemplatePage>().toEqualTypeOf<TemplatePage>();
    expectTypeOf<TemplateRect>().toEqualTypeOf<TemplateRect>();
  });

  it("shares the editable template lifecycle predicate", () => {
    expect(isEditableTemplateStatus("DRAFT")).toBe(true);
    expect(isEditableTemplateStatus("PREFLIGHT_FAILED")).toBe(true);
    expect(isEditableTemplateStatus("READY_TO_PUBLISH")).toBe(true);
    expect(isEditableTemplateStatus("PUBLISHED")).toBe(false);
  });

  it("creates a template draft through the versioned api", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ version_id: "TPL-1", status: "DRAFT", fields: [], artifacts: [] }), {
        status: 201,
        headers: { "content-type": "application/json" },
      }),
    );
    const api = new TemplateApi("/api/v1", fetcher);

    const created = await api.createDraft("PAYROLL_HOURLY", "A4");

    expect(fetcher).toHaveBeenCalledWith("/api/v1/templates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_key: "PAYROLL_HOURLY", page_size: "A4" }),
    });
    expect(created.version_id).toBe("TPL-1");
  });

  it("reads the template library with GET", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));

    await new TemplateApi("/api/v1", fetcher).listTemplates();

    expect(fetcher).toHaveBeenCalledWith("/api/v1/templates", {
      method: "GET",
      headers: {},
    });
  });

  it("clones a published version with POST and no body", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ version_id: "TPL-2" }), { status: 201 }));

    await new TemplateApi("/api/v1", fetcher).clone("TPL/1");

    expect(fetcher).toHaveBeenCalledWith("/api/v1/template-versions/TPL%2F1/clone", {
      method: "POST",
      headers: {},
    });
  });

  it("replaces and deletes fields through their versioned endpoints", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ version_id: "TPL-1" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ version_id: "TPL-1" }), { status: 200 }));
    const api = new TemplateApi("/api/v1", fetcher);
    const field: TemplateField = {
      field_key: "worker_name",
      display_name: "Worker name",
      data_type: "text",
      input_type: "text_box",
      recognition_engine: "manual",
      minimum_prefill_confidence: 0.97,
      rules: {
        required: false,
        minimum_value: null,
        maximum_value: null,
        allowed_values: [],
        master_data_source: null,
        allow_exception_reason: false,
      },
      export_target: {
        workbook: "records.xlsx",
        worksheet: "records",
        business_column: "worker_name",
      },
      region: { x: 0.1, y: 0.2, width: 0.22, height: 0.05 },
    };

    await api.replaceField("TPL-1", "worker/name", field);
    await api.deleteField("TPL-1", "worker/name");

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/v1/template-versions/TPL-1/fields/worker%2Fname", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(field),
    });
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/v1/template-versions/TPL-1/fields/worker%2Fname", {
      method: "DELETE",
      headers: {},
    });
  });

  it("surfaces structured API errors from every request method", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: "NOT_FOUND", detail: "Missing template" }), { status: 404 }));

    await expect(new TemplateApi("/api/v1", fetcher).getVersion("missing")).rejects.toEqual(
      expect.objectContaining({ status: 404, code: "NOT_FOUND", message: "Missing template" }),
    );
  });
});
