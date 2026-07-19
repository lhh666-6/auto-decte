import { describe, expect, it, vi } from "vitest";

import { ImportApi } from "@form-detection/api-client";

describe("ImportApi", () => {
  it("uploads one batch item with stable batch metadata", async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({
      form_id: "FORM-1", task_id: "TASK-1",
    }), { status: 202 }));
    const file = new File(["image"], "车间 1.png", { type: "image/png" });

    const result = await new ImportApi("/api/v1", fetcher).uploadImage(file, "BATCH-1", "ITEM-1");

    expect(result).toEqual({ status: "SUCCEEDED", form_id: "FORM-1", task_id: "TASK-1" });
    expect(fetcher).toHaveBeenCalledWith("/api/v1/imports", expect.objectContaining({
      method: "POST",
      body: file,
      headers: expect.objectContaining({
        "X-Import-Batch-ID": "BATCH-1",
        "X-Original-Filename": encodeURIComponent("车间 1.png"),
      }),
    }));
  });

  it("returns duplicate images as an actionable item", async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({
      code: "DUPLICATE_EVIDENCE",
      detail: "图片重复",
      task_id: "TASK-D",
      existing_form: { form_id: "FORM-OLD" },
    }), { status: 409 }));
    const file = new File(["image"], "same.png", { type: "image/png" });

    await expect(new ImportApi("/api/v1", fetcher).uploadImage(file, "BATCH-1", "ITEM-D"))
      .resolves.toEqual({
        status: "NEEDS_ACTION",
        form_id: "FORM-OLD",
        task_id: "TASK-D",
        detail: "图片重复",
      });
  });
});
