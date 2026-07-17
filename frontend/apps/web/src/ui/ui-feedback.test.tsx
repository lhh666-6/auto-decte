// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";
import { ProblemNotice } from "./ProblemNotice";

afterEach(cleanup);

describe("shared feedback", () => {
  it("gives every problem a title, reason, next action and trace-only code", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    render(
      <ProblemNotice
        title="导出没有完成"
        reason="文件服务暂时不可用。"
        actionLabel="重新生成 Excel"
        onAction={retry}
        code="EXPORT_WRITE_FAILED"
      />,
    );

    expect(screen.getByRole("alert").textContent).toContain("导出没有完成");
    expect(screen.getByRole("alert").textContent).toContain("文件服务暂时不可用。");
    expect(screen.queryByText("EXPORT_WRITE_FAILED")).toBeNull();
    await user.click(screen.getByText("追溯详情"));
    expect(screen.getByText("EXPORT_WRITE_FAILED")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "重新生成 Excel" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("focuses an explicit confirmation, cancels with Escape and restores trigger focus", async () => {
    const user = userEvent.setup();
    const confirm = vi.fn();

    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>停用基础数据</button>
          {open ? (
            <ConfirmDialog
              title="停用当前基础数据"
              description="停用后不会删除历史记录。"
              confirmLabel="确认停用基础数据"
              onCancel={() => setOpen(false)}
              onConfirm={confirm}
            />
          ) : null}
        </>
      );
    }

    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "停用基础数据" });
    await user.click(trigger);
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "停用当前基础数据" }));
    expect(screen.getByText("停用后不会删除历史记录。")).toBeTruthy();
    expect(screen.getByRole("button", { name: "取消停用" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "确认停用基础数据" })).toBeTruthy();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
