import { describe, expect, it, vi } from "vitest";

import { ApiRequestError, ReviewWorkbenchApi } from "../../../packages/api-client/src/review-workbench";

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

  it("uses real review workflow and classification endpoints", async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    ));
    const api = new ReviewWorkbenchApi("/api/v1", fetcher);

    await api.saveDraft("FORM-1", {
      expectedVersion: 0,
      leaseToken: "lease-a",
      values: { work_date: "2026-07-15" },
    });
    await api.returnForm("FORM-1", {
      expectedVersion: 0,
      leaseToken: "lease-a",
      reason: "重新拍摄",
      evidenceIds: [],
    });
    await api.voidForm("FORM-2", {
      expectedVersion: 1,
      leaseToken: "lease-b",
      reason: "重复表单",
      evidenceIds: [],
    });
    await api.confirmAndClaimNext("FORM-3", {
      expectedVersion: 0,
      leaseToken: "lease-c",
      values: { work_date: "2026-07-15" },
      reason: "确认",
      evidenceIds: [],
      queueKey: "review",
    });
    await api.getClassificationOptions("FORM-4");
    await api.assignTemplate("FORM-4", {
      templateKey: "PAYROLL_HOURLY",
      version: 1,
      reason: "二维码损坏",
    });

    expect(fetcher.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/forms/FORM-1/review-draft",
      "/api/v1/forms/FORM-1/return",
      "/api/v1/forms/FORM-2/void",
      "/api/v1/forms/FORM-3/confirm-and-claim-next",
      "/api/v1/forms/FORM-4/classification-options",
      "/api/v1/forms/FORM-4/assign-template",
    ]);
  });

  it("preserves field-level template rule failures", async () => {
    const failures = [{ code: "NOT_ALLOWED", field_key: "shift", message: "字段值不在模板允许范围内" }];
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      code: "REVIEW_RULE_BLOCKED",
      detail: "模板规则已阻止审核确认",
      failures,
    }), { status: 422, headers: { "content-type": "application/problem+json" } }));

    const request = new ReviewWorkbenchApi("/api/v1", fetcher).confirmAndClaimNext("FORM-1", {
      expectedVersion: 0,
      leaseToken: "lease-a",
      values: { shift: "1" },
      reason: "确认",
      evidenceIds: [],
      queueKey: "review",
    });

    await expect(request).rejects.toEqual(expect.objectContaining({
      code: "REVIEW_RULE_BLOCKED",
      failures,
    } satisfies Partial<ApiRequestError>));
  });
});
