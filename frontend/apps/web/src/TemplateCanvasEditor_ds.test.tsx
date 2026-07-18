// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TemplateVersion } from "@form-detection/api-client";

import { TemplateCanvasEditor } from "./TemplateCanvasEditor_ds";
import { createFieldDraft } from "./template-studio-model";

const FIELD = { ...createFieldDraft([]), field_key: "hours", display_name: "工时" };
const VERSION = {
  version_id: "VERSION-1",
  template_key: "PAYROLL",
  display_name: "计时工资表",
  description: "",
  version: 1,
  status: "DRAFT",
  parent_version_id: null,
  page: { size: "A4", orientation: "portrait", width_mm: 210, height_mm: 297, canonical_dpi: 300, canonical_width_px: 2480, canonical_height_px: 3508 },
  static_elements: [],
  print_imposition: null,
  fields: [FIELD],
  artifacts: [],
} satisfies TemplateVersion;

afterEach(cleanup);

describe("TemplateCanvasEditor", () => {
  it("offers millimeter rulers, snap, zoom, alignment, undo and redo", async () => {
    const user = userEvent.setup();
    const persist = vi.fn().mockResolvedValue(undefined);
    render(<TemplateCanvasEditor version={VERSION} selectedFieldKey="hours" editable onSelect={vi.fn()} onPersist={persist} onReject={vi.fn()} />);

    expect(screen.getByLabelText("横向毫米标尺")).toBeTruthy();
    expect(screen.getByLabelText("纵向毫米标尺")).toBeTruthy();
    expect(screen.getByRole("button", { name: "网格吸附" }).getAttribute("aria-pressed")).toBe("true");

    await user.click(screen.getByRole("button", { name: "放大画布" }));
    expect(screen.getByTestId("template-canvas-paper").getAttribute("style")).toContain("scale(1.1)");

    await user.click(screen.getByRole("button", { name: "水平居中" }));
    await waitFor(() => expect(persist).toHaveBeenCalledWith(FIELD, { x: 0.39, y: 0.2, width: 0.22, height: 0.05 }));
    await user.click(screen.getByRole("button", { name: "撤销" }));
    await waitFor(() => expect(persist).toHaveBeenLastCalledWith(FIELD, FIELD.region));
    await user.click(screen.getByRole("button", { name: "重做" }));
    await waitFor(() => expect(persist).toHaveBeenCalledTimes(3));
  });

  it("keeps published versions read-only", () => {
    render(<TemplateCanvasEditor version={{ ...VERSION, status: "PUBLISHED" }} selectedFieldKey="hours" editable={false} onSelect={vi.fn()} onPersist={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByRole("button", { name: "左对齐" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByTestId("template-canvas-paper").className).toContain("read-only");
  });
});
