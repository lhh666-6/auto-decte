import { describe, expect, it, vi } from "vitest";

import { TemplateApi } from "../../../packages/api-client/src/templates_ds";

describe("TemplateApi", () => {
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
});
