// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportApi } from "@form-detection/api-client";

import { BatchImportPanel } from "./BatchImportPanel";

afterEach(cleanup);

describe("BatchImportPanel", () => {
  it("runs at most three image imports concurrently and keeps per-image results", async () => {
    const user = userEvent.setup();
    const pending: Array<(response: Response) => void> = [];
    let active = 0;
    let maximumActive = 0;
    const fetcher = vi.fn(() => new Promise<Response>((resolve) => {
      active += 1;
      maximumActive = Math.max(maximumActive, active);
      pending.push((response) => { active -= 1; resolve(response); });
    }));
    render(<BatchImportPanel api={new ImportApi("/api/v1", fetcher)} onClose={vi.fn()} onChanged={vi.fn()} />);
    const files = Array.from({ length: 4 }, (_, index) => new File(
      [`image-${index}`], `image-${index}.png`, { type: "image/png" },
    ));

    await user.upload(screen.getByLabelText("选择多张照片"), files);
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));
    expect(maximumActive).toBe(3);
    pending.splice(0).forEach((resolve, index) => resolve(jsonResponse({ form_id: `FORM-${index}`, task_id: `TASK-${index}` }, 202)));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(4));
    pending.splice(0).forEach((resolve) => resolve(jsonResponse({ form_id: "FORM-4", task_id: "TASK-4" }, 202)));

    await screen.findByText("成功 4｜处理中 0｜需要处理 0｜失败 0");
    expect(maximumActive).toBe(3);
  });
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}
