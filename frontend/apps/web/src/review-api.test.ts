import { describe, expect, it, vi } from "vitest";

import { ReviewWorkbenchApi } from "../../../packages/api-client/src/review-workbench";

describe("ReviewWorkbenchApi", () => {
  it("loads a workbench record from the versioned form endpoint", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ form: { form_id: "FORM-1" }, fields: [], evidence: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const api = new ReviewWorkbenchApi("/api/v1", fetcher);

    const detail = await api.getWorkbench("FORM-1");

    expect(fetcher).toHaveBeenCalledWith("/api/v1/forms/FORM-1", { headers: {} });
    expect(detail.form.form_id).toBe("FORM-1");
  });

  it("does not call a fetch implementation as an object method", async () => {
    const nativeLikeFetcher = vi.fn(function (this: unknown) {
      if (this !== undefined) throw new Error("illegal invocation");
      return Promise.resolve(new Response(JSON.stringify({ form: { form_id: "FORM-2" }, fields: [], evidence: [] })));
    });
    const api = new ReviewWorkbenchApi("/api/v1", nativeLikeFetcher);

    const detail = await api.getWorkbench("FORM-2");

    expect(detail.form.form_id).toBe("FORM-2");
  });
});
