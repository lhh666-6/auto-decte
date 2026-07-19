// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TemplateVersion } from "@form-detection/api-client";

import { TemplateStudio } from "./TemplateStudio_ds";
import { createFieldDraft } from "./template-studio-model";

const EXISTING = { ...createFieldDraft([]), field_key: "hours", display_name: "工时", export_target: { ...createFieldDraft([]).export_target, business_column: "hours" } };
const VERSION = {
  version_id: "VERSION-1",
  template_key: "PAYROLL",
  display_name: "计时工资表",
  description: "车间计时工资",
  version: 1,
  status: "DRAFT",
  parent_version_id: null,
  page: { size: "A4", orientation: "portrait", width_mm: 210, height_mm: 297, canonical_dpi: 300, canonical_width_px: 2480, canonical_height_px: 3508 },
  static_elements: [],
  print_imposition: null,
  fields: [EXISTING],
  artifacts: [],
} satisfies TemplateVersion;

const GRID_VERSION = {
  ...VERSION,
  fields: [],
  static_elements: [{
    element_id: "detail_grid",
    kind: "TABLE_GRID",
    text: "Production detail",
    rows: 3,
    columns: 3,
    column_weights: [2, 1, 1],
    region: { x: 0.1, y: 0.3, width: 0.8, height: 0.4 },
  }],
} satisfies TemplateVersion;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TemplateStudio field creation", () => {
  it("selects an existing controlled grid and persists its settings", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        const body = JSON.parse(String(init.body)) as typeof GRID_VERSION.static_elements[number];
        return jsonResponse({ ...GRID_VERSION, static_elements: [body] });
      }
      return jsonResponse(GRID_VERSION);
    });
    vi.stubGlobal("fetch", fetcher);
    render(<TemplateStudio initialScreen={{ kind: "editor", versionId: "VERSION-1" }} />);

    await user.click(await screen.findByRole("button", { name: /Production detail/ }));
    await user.clear(screen.getByLabelText("表格行数"));
    await user.type(screen.getByLabelText("表格行数"), "4");
    await user.click(screen.getByRole("button", { name: "保存表格设置" }));

    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    expect(fetcher.mock.calls[1]?.[0]).toBe("/api/v1/template-versions/VERSION-1/static-elements/detail_grid");
    expect(JSON.parse(String(fetcher.mock.calls[1]?.[1]?.body))).toEqual(
      expect.objectContaining({ rows: 4, columns: 3, column_weights: [2, 1, 1] }),
    );
  });

  it("uses an independent draft and rejects duplicate keys before the API call", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn(async () => jsonResponse(VERSION));
    vi.stubGlobal("fetch", fetcher);
    render(<TemplateStudio initialScreen={{ kind: "editor", versionId: "VERSION-1" }} />);

    expect(await screen.findByText("草稿")).toBeTruthy();
    expect(screen.queryByText("DRAFT")).toBeNull();
    await user.click(await screen.findByRole("button", { name: "＋ 添加业务字段" }));
    const dialog = screen.getByRole("dialog", { name: "添加业务字段" });
    expect((within(dialog).getByLabelText("字段键") as HTMLInputElement).value).toBe("field_2");
    expect((within(dialog).getByLabelText("显示名") as HTMLInputElement).value).toBe("新字段 2");

    await user.clear(within(dialog).getByLabelText("字段键"));
    await user.type(within(dialog).getByLabelText("字段键"), "hours");
    await user.click(within(dialog).getByRole("button", { name: "添加字段" }));
    expect((await screen.findByRole("alert")).textContent).toContain("已存在");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("guards rapid double clicks and rolls back the canvas when creation fails", async () => {
    const user = userEvent.setup();
    const failed = deferred<Response>();
    const fetcher = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") return failed.promise;
      return Promise.resolve(jsonResponse(VERSION));
    });
    vi.stubGlobal("fetch", fetcher);
    render(<TemplateStudio initialScreen={{ kind: "editor", versionId: "VERSION-1" }} />);

    await user.click(await screen.findByRole("button", { name: "＋ 添加业务字段" }));
    const add = within(screen.getByRole("dialog", { name: "添加业务字段" })).getByRole("button", { name: "添加字段" });
    fireEvent.click(add);
    fireEvent.click(add);
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    failed.resolve(jsonResponse({ code: "DUPLICATE_FIELD", detail: "duplicate" }, 409));

    expect((await screen.findByRole("alert")).textContent).toContain("模板请求无法完成");
    expect(screen.getByRole("dialog", { name: "添加业务字段" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "选择字段 工时" }).getAttribute("aria-pressed")).toBe("true");
    await waitFor(() => expect(screen.getAllByText("工时").length).toBeGreaterThan(0));
  });
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
