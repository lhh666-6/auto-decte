import { describe, expect, expectTypeOf, it, vi } from "vitest";

import { isEditableTemplateStatus } from "@form-detection/api-client";
import type {
  FillPolicy,
  PaperEntryMode,
  RecognitionMode,
  TemplateField,
  TemplateFieldInput,
  TemplateLibraryItem,
  TemplatePage,
  TemplatePageInput,
  TemplatePrintImposition,
  TemplateRect,
  TemplateStaticElement,
} from "@form-detection/api-client";
import { TemplateApi } from "../../../packages/api-client/src/templates_ds";

describe("TemplateApi", () => {
  it("re-exports the template contracts from the package entry point", () => {
    expectTypeOf<TemplateField>().toEqualTypeOf<TemplateField>();
    expectTypeOf<PaperEntryMode>().toEqualTypeOf<PaperEntryMode>();
    expectTypeOf<RecognitionMode>().toEqualTypeOf<RecognitionMode>();
    expectTypeOf<FillPolicy>().toEqualTypeOf<FillPolicy>();
    expectTypeOf<TemplateFieldInput>().toEqualTypeOf<TemplateFieldInput>();
    expectTypeOf<TemplateLibraryItem>().toEqualTypeOf<TemplateLibraryItem>();
    expectTypeOf<TemplatePage>().toEqualTypeOf<TemplatePage>();
    expectTypeOf<TemplatePageInput>().toEqualTypeOf<TemplatePageInput>();
    expectTypeOf<TemplateStaticElement>().toEqualTypeOf<TemplateStaticElement>();
    expectTypeOf<TemplatePrintImposition>().toEqualTypeOf<TemplatePrintImposition>();
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

    const created = await api.createDraft("PAYROLL_HOURLY", "A4", "计时工资单", "计时记录");

    expect(fetcher).toHaveBeenCalledWith("/api/v1/templates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template_key: "PAYROLL_HOURLY",
        page_size: "A4",
        display_name: "计时工资单",
        description: "计时记录",
      }),
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

  it("creates a custom physical page with a typed request", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ version_id: "TPL-CUSTOM" }), { status: 201 }),
    );
    const api = new TemplateApi("/api/v1", fetcher);
    const page: TemplatePageInput = {
      size: "CUSTOM",
      orientation: "landscape",
      width_mm: 123.4,
      height_mm: 87.6,
      canonical_dpi: 300,
    };

    await api.createDraftForPage("PAYROLL_CUSTOM", page, "自定义工资表", "横向小表");

    expect(fetcher).toHaveBeenCalledWith("/api/v1/templates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template_key: "PAYROLL_CUSTOM",
        page,
        display_name: "自定义工资表",
        description: "横向小表",
      }),
    });
  });

  it("updates metadata, discards drafts and retires templates", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ template_key: "T1" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const api = new TemplateApi("/api/v1", fetcher);

    await api.updateMetadata("T/1", "中文名称", "用途");
    await api.discardDraft("D/1");
    await api.retireTemplate("T/1");

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/v1/templates/T%2F1", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: "中文名称", description: "用途" }),
    });
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/v1/template-versions/D%2F1", {
      method: "DELETE",
      headers: {},
    });
    expect(fetcher).toHaveBeenNthCalledWith(3, "/api/v1/templates/T%2F1/retire", {
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
      paper_entry_mode: "HANDWRITTEN_TEXT",
      recognition_mode: "NONE",
      fill_policy: "MANUAL_ONLY",
      confidence_threshold: null,
      requires_manual_confirmation: true,
      calculation_expression: null,
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
