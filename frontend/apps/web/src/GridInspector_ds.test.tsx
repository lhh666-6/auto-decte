// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TemplateStaticElement } from "@form-detection/api-client";

import { GridInspector } from "./GridInspector_ds";

const GRID: TemplateStaticElement = {
  element_id: "detail_grid",
  kind: "TABLE_GRID",
  text: "生产明细",
  rows: 3,
  columns: 3,
  column_weights: [2, 1, 1],
  region: { x: 0.1, y: 0.3, width: 0.8, height: 0.4 },
};

afterEach(cleanup);

describe("GridInspector", () => {
  it("saves only positive row, column and proportional width settings", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn(async () => undefined);
    render(<GridInspector grid={GRID} editable onSave={onSave} />);

    await user.clear(screen.getByLabelText("表格行数"));
    await user.type(screen.getByLabelText("表格行数"), "4");
    await user.clear(screen.getByLabelText("表格比例列宽"));
    await user.type(screen.getByLabelText("表格比例列宽"), "3:2:1");
    await user.click(screen.getByRole("button", { name: "保存表格设置" }));

    expect(onSave).toHaveBeenCalledWith({ ...GRID, rows: 4, column_weights: [3, 2, 1] });
  });

  it("rejects a width list that does not match the controlled column count", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn(async () => undefined);
    render(<GridInspector grid={GRID} editable onSave={onSave} />);

    await user.clear(screen.getByLabelText("表格比例列宽"));
    await user.type(screen.getByLabelText("表格比例列宽"), "1:1");
    await user.click(screen.getByRole("button", { name: "保存表格设置" }));

    expect(screen.getByRole("alert").textContent).toContain("3 个");
    expect(onSave).not.toHaveBeenCalled();
  });
});
