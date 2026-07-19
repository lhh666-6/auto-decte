// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportApi } from "@form-detection/api-client";

import { ImageOverview, ImportBatchOverview } from "./ImportOverview";

afterEach(cleanup);

describe("import overview", () => {
  it("opens a form directly from the thumbnail wall", async () => {
    const user = userEvent.setup();
    const onOpenForm = vi.fn();
    const api = new ImportApi("/api/v1", async () => jsonResponse([{
      form_id: "FORM-1", file_name: "工资表.png", review_status: "NEEDS_REVIEW",
      template_id: "PAYROLL", template_version: "2", created_at: "2026-07-20T00:00:00Z",
      thumbnail_url: "/thumb.jpg", original_url: "/original.png",
    }]));
    render(<ImageOverview api={api} onOpenForm={onOpenForm} />);

    await user.click(await screen.findByRole("button", { name: /工资表.png/ }));

    expect(onOpenForm).toHaveBeenCalledWith("FORM-1");
  });

  it("shows persisted aggregate and item statuses for each batch", async () => {
    const api = new ImportApi("/api/v1", async () => jsonResponse([{
      batch_id: "BATCH-1", created_at: "2026-07-20T00:00:00Z",
      counts: { total: 3, succeeded: 2, processing: 0, needs_action: 1, failed: 0 },
      items: [{ task_id: "TASK-1", form_id: "FORM-1", file_name: "重复.png", content_type: "image/png", size_bytes: 10, width: 20, height: 20, status: "NEEDS_ACTION", review_status: "NEEDS_REVIEW", thumbnail_url: null, error: "重复" }],
    }]));
    render(<ImportBatchOverview api={api} />);

    expect(await screen.findByText("成功 2｜处理中 0｜需要处理 1｜失败 0")).toBeTruthy();
    expect(screen.getByText("本次导入 3 张")).toBeTruthy();
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}
