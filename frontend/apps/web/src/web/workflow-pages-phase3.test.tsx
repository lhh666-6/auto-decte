// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { BusinessModelingPage } from "./BusinessModelingPage";
import { WorkflowDesignerPage } from "./WorkflowDesignerPage";

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("keeps discovered rules non-executable until finance confirms them", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(response({ session_id: "discovery-1" }))
    .mockResolvedValueOnce(response({
      assistant_message: "待确认",
      proposed_rules: [{
        rule_id: "rule-1",
        content_json: { statement: "主管审核后释放笼号" },
        confidence: 50,
        status: "PROPOSED",
        executable: false,
      }],
    }))
    .mockResolvedValueOnce(response({ baseline: { version: 1, status: "CONFIRMED" } })));
  const user = userEvent.setup();
  render(<BusinessModelingPage />);

  await user.type(screen.getByLabelText("业务说明"), "主管审核后释放笼号");
  await user.click(screen.getByRole("button", { name: "生成待确认规则" }));
  expect(await screen.findByText("不可执行草稿")).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "确认并生成业务基线" }));
  expect(await screen.findByText("财务已确认")).toBeTruthy();
});

it("builds structured cards and shows workflow preflight result", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(response({ version_id: "workflow-v1" }))
    .mockResolvedValueOnce(response({ valid: true, errors: [] })));
  const user = userEvent.setup();
  render(<WorkflowDesignerPage />);

  await user.click(screen.getByRole("button", { name: "添加通知节点" }));
  await user.click(screen.getByRole("button", { name: "添加结束节点" }));
  await user.click(screen.getByRole("button", { name: "保存并预检" }));

  expect(await screen.findByText(/流程预检通过/)).toBeTruthy();
});
