// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TemplateApi, TemplateLibraryItem } from "@form-detection/api-client";

import { TemplateLibrary } from "./TemplateLibrary_ds";

const ITEM = {
  template_key: "PAYROLL_HOURLY",
  display_name: "小时工资表",
  description: "车间小时工资采集",
  version_id: "VERSION-1",
  current_published_version: 1,
  version: 1,
  status: "PUBLISHED",
  page: {
    size: "A4", orientation: "portrait", width_mm: 210, height_mm: 297,
    canonical_dpi: 300, canonical_width_px: 2480, canonical_height_px: 3508,
  },
  field_count: 8,
  active_draft: null,
} satisfies TemplateLibraryItem;

afterEach(cleanup);

describe("TemplateLibrary", () => {
  it("uses a compact top toolbar and opens template creation on demand", async () => {
    const user = userEvent.setup();
    const onCreateBlank = vi.fn().mockResolvedValue(undefined);
    const api = { listTemplates: vi.fn().mockResolvedValue([ITEM]) } as unknown as TemplateApi;
    render(
      <TemplateLibrary
        api={api}
        onBack={vi.fn()}
        onSelectPublished={vi.fn()}
        onOpenDraft={vi.fn()}
        onCreateBlank={onCreateBlank}
      />,
    );

    expect(await screen.findByRole("heading", { name: "小时工资表" })).toBeTruthy();
    expect(screen.getByLabelText("搜索模板")).toBeTruthy();
    expect(screen.getByLabelText("模板状态筛选")).toBeTruthy();
    const importButton = screen.getByRole("button", { name: /导入模板包.*暂未开放/ }) as HTMLButtonElement;
    expect(importButton.disabled).toBe(true);
    expect(screen.queryByRole("dialog", { name: "创建模板" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "创建模板" }));
    expect(screen.getByRole("dialog", { name: "创建模板" })).toBeTruthy();
    await user.clear(screen.getByLabelText("模板名称"));
    await user.type(screen.getByLabelText("模板名称"), "计件工资表");
    await user.clear(screen.getByLabelText("模板编号"));
    await user.type(screen.getByLabelText("模板编号"), "payroll_piece");
    await user.click(screen.getByRole("button", { name: "创建空白模板" }));
    await waitFor(() => expect(onCreateBlank).toHaveBeenCalledWith(
      "PAYROLL_PIECE", "A4", "计件工资表", "",
    ));
  });

  it("puts the Chinese name first and keeps one main action with dangerous actions under More", async () => {
    const user = userEvent.setup();
    const api = { listTemplates: vi.fn().mockResolvedValue([ITEM]) } as unknown as TemplateApi;
    render(
      <TemplateLibrary api={api} onBack={vi.fn()} onSelectPublished={vi.fn()} onOpenDraft={vi.fn()} onCreateBlank={vi.fn()} />,
    );

    const card = (await screen.findByRole("heading", { name: "小时工资表" })).closest("article")!;
    expect(card.textContent?.indexOf("小时工资表")).toBeLessThan(card.textContent?.indexOf("PAYROLL_HOURLY") ?? 0);
    expect(card.querySelectorAll(".template-card-actions > .button")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "退役模板" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "更多" }));
    expect(screen.getByRole("button", { name: "退役模板" })).toBeTruthy();
  });
});
