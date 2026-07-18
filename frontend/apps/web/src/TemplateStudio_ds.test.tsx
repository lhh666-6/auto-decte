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

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TemplateStudio field creation", () => {
  it("uses an independent draft and rejects duplicate keys before the API call", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn(async () => jsonResponse(VERSION));
    vi.stubGlobal("fetch", fetcher);
    render(<TemplateStudio initialScreen={{ kind: "editor", versionId: "VERSION-1" }} />);

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
