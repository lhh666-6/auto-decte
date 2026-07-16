// @vitest-environment jsdom

import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ExportBatch,
  ExportPreview,
  ExportTask,
} from "@form-detection/api-client";

import { ExportCenter, type ExportCenterApi } from "./ExportCenter_ds";
import { App } from "./App";

const preview: ExportPreview = {
  included: [{ form_id: "FORM-1", record_version: 2, reasons: [] }],
  excluded: [{
    form_id: "FORM-2",
    record_version: 1,
    reason: "RULE_BLOCKED",
    reasons: [
      { scope: "FORM", code: "NOT_CONFIRMED", message: "表单尚未确认" },
      {
        scope: "FIELD",
        code: "NOT_ALLOWED",
        field_key: "shift",
        message: "班次不在模板允许范围内",
        required: true,
        allowed_values: ["A", "B"],
        minimum_value: 1,
        maximum_value: 10,
      },
    ],
  }],
  mapping_snapshot: [{
    template_id: "PAYROLL_HOURLY",
    template_version: "1",
    field_key: "employee_id",
    workbook: "企业工资记录.xlsx",
    worksheet: "计时考核单",
    business_column: "employee_id",
  }],
};

const oldBatch: ExportBatch = {
  export_batch_id: "BATCH-OLD",
  export_type: "PAYROLL",
  task_id: "TASK-OLD",
  template_snapshot: { template_id: "PAYROLL_HOURLY", version: 1 },
  mapping_snapshot: [],
  mapping_hash: "mapping-hash",
  filters: { export_status: "NOT_EXPORTED" },
  included_records: [{ form_id: "FORM-1", record_version: 1 }],
  file_sha256: "file-sha",
  exported_by: "finance-user",
  exported_at: "2026-07-16T08:00:00Z",
  supersedes_batch_id: null,
  download_url: "/api/v1/exports/batches/BATCH-OLD/download",
  download_name: "payroll-old.xlsx",
};

const succeededTask: ExportTask = {
  task_id: "TASK-NEW",
  operation: "XLSX_EXPORT",
  resource_id: "EXPORTS",
  status: "SUCCEEDED",
  progress: 100,
  step: "COMPLETE",
  error: null,
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function makeApi(overrides: Partial<ExportCenterApi> = {}): ExportCenterApi {
  return {
    preview: vi.fn().mockResolvedValue(preview),
    create: vi.fn().mockResolvedValue({
      task_id: "TASK-NEW",
      status: "PENDING",
      status_url: "/api/v1/tasks/TASK-NEW",
      events_url: "/api/v1/tasks/TASK-NEW/events",
    }),
    waitForTask: vi.fn().mockResolvedValue(succeededTask),
    listBatches: vi.fn().mockResolvedValue([oldBatch]),
    getBatch: vi.fn().mockResolvedValue(oldBatch),
    downloadBatch: vi.fn().mockResolvedValue(new Blob(["xlsx"])),
    ...overrides,
  };
}

describe("ExportCenter", () => {
  it("defaults preview and ordinary create to NOT_EXPORTED without an ALL bypass", async () => {
    const user = userEvent.setup();
    const api = makeApi();
    render(<ExportCenter api={api} onBack={vi.fn()} />);

    const status = screen.getByLabelText("导出状态") as HTMLSelectElement;
    expect(status.value).toBe("NOT_EXPORTED");
    expect(within(status).queryByRole("option", { name: "全部" })).toBeNull();
    await user.type(screen.getByLabelText("表单编号"), "FORM-1");
    await user.clear(screen.getByLabelText("表单编号"));
    await user.click(screen.getByRole("button", { name: "预览导出范围" }));

    expect(api.preview).toHaveBeenCalledWith(expect.objectContaining({
      export_status: "NOT_EXPORTED",
    }));
    await user.click(await screen.findByRole("button", { name: "创建导出任务" }));
    await waitFor(() => expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({ export_status: "NOT_EXPORTED" }),
      }),
      expect.any(String),
    ));
  });

  it("previews included records, FORM/FIELD exclusions, rule details and mappings", async () => {
    const user = userEvent.setup();
    const api = makeApi();
    render(<ExportCenter api={api} onBack={vi.fn()} />);

    await user.type(screen.getByLabelText("表单编号"), "FORM/一");
    await user.type(screen.getByLabelText("员工编号"), "E&01");
    await user.click(screen.getByRole("button", { name: "预览导出范围" }));

    expect(api.preview).toHaveBeenCalledWith(expect.objectContaining({
      form_id: "FORM/一",
      employee_id: "E&01",
    }));
    expect(await screen.findByText("FORM-1 · 记录版本 2")).toBeTruthy();
    const excluded = screen.getByRole("region", { name: "排除记录" });
    expect(within(excluded).getByText("FORM-2 · 记录版本 1")).toBeTruthy();
    expect(within(excluded).getByText("FORM · NOT_CONFIRMED")).toBeTruthy();
    expect(within(excluded).getByText("FIELD · shift · NOT_ALLOWED")).toBeTruthy();
    expect(within(excluded).getByText("必填；允许值：A、B；范围：1–10")).toBeTruthy();
    expect(screen.getByText("企业工资记录.xlsx / 计时考核单 / employee_id")).toBeTruthy();
  });

  it("creates an export, renders live task progress, refreshes history and downloads a Blob", async () => {
    const user = userEvent.setup();
    let finishTask!: (task: ExportTask) => void;
    const pendingTask = new Promise<ExportTask>((resolve) => { finishTask = resolve; });
    const waitForTask = vi.fn().mockImplementation(async (
      _taskId: string,
      options?: { onUpdate?: (task: ExportTask) => void },
    ) => {
      options?.onUpdate?.({ ...succeededTask, status: "RUNNING", progress: 55, step: "WRITE_WORKBOOK" });
      return pendingTask;
    });
    const api = makeApi({ waitForTask });
    const createObjectURL = vi.fn().mockReturnValue("blob:export");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<ExportCenter api={api} onBack={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "预览导出范围" }));
    await user.click(await screen.findByRole("button", { name: "创建导出任务" }));

    expect(await screen.findByText("WRITE_WORKBOOK")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("55");
    await act(async () => { finishTask(succeededTask); });
    expect(await screen.findByText("导出任务已完成。" )).toBeTruthy();
    expect(api.listBatches).toHaveBeenCalledTimes(2);

    const history = screen.getByRole("region", { name: "导出批次历史" });
    expect(within(history).getByText("BATCH-OLD")).toBeTruthy();
    await user.click(within(history).getByRole("button", { name: "下载 payroll-old.xlsx" }));
    await waitFor(() => expect(api.downloadBatch).toHaveBeenCalledWith("BATCH-OLD"));
    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
  });

  it("shows REEXPORT_REQUIRED and submits the actual source batch as supersedes_batch_id", async () => {
    const user = userEvent.setup();
    const api = makeApi();
    render(<ExportCenter api={api} onBack={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("导出状态"), "REEXPORT_REQUIRED");
    await user.click(screen.getByRole("button", { name: "预览导出范围" }));

    expect((await screen.findByRole("alert")).textContent).toContain("REEXPORT_REQUIRED");
    const ordinaryCreate = screen.getByRole("button", { name: "创建导出任务" });
    expect(ordinaryCreate.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("重导必须从下方选择一个覆盖全部表单旧版本的来源批次。")).toBeTruthy();
    await user.click(ordinaryCreate);
    expect(api.create).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "重导并替代 BATCH-OLD" }));

    await waitFor(() => expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({ export_status: "REEXPORT_REQUIRED" }),
        supersedes_batch_id: "BATCH-OLD",
      }),
      expect.any(String),
    ));
  });

  it("rejects a re-export source that lacks an older version for every included form", async () => {
    const user = userEvent.setup();
    const multiPreview: ExportPreview = {
      ...preview,
      included: [
        { form_id: "FORM-1", record_version: 2, reasons: [] },
        { form_id: "FORM-2", record_version: 3, reasons: [] },
      ],
    };
    const partialBatch: ExportBatch = {
      ...oldBatch,
      export_batch_id: "BATCH-PARTIAL",
      included_records: [
        { form_id: "FORM-1", record_version: 1 },
        { form_id: "FORM-2", record_version: 3 },
      ],
    };
    const api = makeApi({
      preview: vi.fn().mockResolvedValue(multiPreview),
      listBatches: vi.fn().mockResolvedValue([partialBatch]),
    });
    render(<ExportCenter api={api} onBack={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("导出状态"), "REEXPORT_REQUIRED");
    await user.click(screen.getByRole("button", { name: "预览导出范围" }));

    expect(screen.queryByRole("button", { name: "重导并替代 BATCH-PARTIAL" })).toBeNull();
    const disabledSource = screen.getByRole("button", { name: "不可作为来源 BATCH-PARTIAL" });
    expect(disabledSource.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("该批次未包含每个拟重导表单的旧版本，请缩小筛选范围。")).toBeTruthy();
    await user.click(disabledSource);
    expect(api.create).not.toHaveBeenCalled();
  });

  it("aborts task polling on unmount without refreshing history afterward", async () => {
    const user = userEvent.setup();
    let pollingSignal: AbortSignal | undefined;
    const waitForTask = vi.fn().mockImplementation((
      _taskId: string,
      options?: { signal?: AbortSignal },
    ) => {
      pollingSignal = options?.signal;
      return new Promise<ExportTask>((_resolve, reject) => {
        pollingSignal?.addEventListener("abort", () => {
          reject(new DOMException("Polling cancelled", "AbortError"));
        }, { once: true });
      });
    });
    const api = makeApi({ waitForTask });
    const rendered = render(<ExportCenter api={api} onBack={vi.fn()} />);

    await waitFor(() => expect(api.listBatches).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "预览导出范围" }));
    await user.click(await screen.findByRole("button", { name: "创建导出任务" }));
    await waitFor(() => expect(waitForTask).toHaveBeenCalledTimes(1));
    rendered.unmount();

    expect(pollingSignal).toBeDefined();
    expect(pollingSignal?.aborted).toBe(true);
    await Promise.resolve();
    expect(api.listBatches).toHaveBeenCalledTimes(1);
  });

  it("opens the export feature from 可导出 only after unsaved review navigation is confirmed", async () => {
    const user = userEvent.setup();
    const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path.includes("/forms/queue/")) return new Response("[]", { status: 200 });
      if (path.endsWith("/forms/FORM-1/review-history")) {
        return new Response(JSON.stringify({ versions: [], audits: [] }), { status: 200 });
      }
      if (path.endsWith("/forms/FORM-1")) {
        return new Response(JSON.stringify({
          form: {
            form_id: "FORM-1",
            template_id: "PAYROLL_HOURLY",
            template_version: "1",
            coordinate_version: "1",
            review_status: "CONFIRMED",
            export_status: "NOT_EXPORTED",
            current_record_version: 1,
            priority: 1,
            created_at: "2026-07-16T00:00:00Z",
          },
          fields: [{
            field_id: "FIELD-1",
            field_name: "hours",
            display_name: "工时",
            data_type: "number",
            recognition_engine: "manual",
            rules: null,
            source_region: { x: 0, y: 0, width: 1, height: 1 },
            current_value: 8,
            current_value_source: "confirmed",
            current_record_version: 1,
            candidates: [],
          }],
          evidence: [],
          current_record: {
            record_id: "RECORD-1",
            version: 1,
            previous_version: null,
            status: "CONFIRMED",
            values: { hours: 8 },
            change_reason: "confirmed",
            confirmed_by: "reviewer",
            created_at: "2026-07-16T00:00:00Z",
          },
          draft: null,
        }), { status: 200 });
      }
      if (path.endsWith("/exports/batches")) return new Response("[]", { status: 200 });
      return new Response(JSON.stringify({ code: "UNEXPECTED", detail: path }), { status: 404 });
    });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<App />);

    await user.type(screen.getByLabelText("表单编号"), "FORM-1");
    await user.click(screen.getByRole("button", { name: "加载表单" }));
    const field = await screen.findByLabelText("工时 确认值");
    await user.clear(field);
    await user.type(field, "9");
    await user.click(screen.getByRole("button", { name: /可导出/ }));

    expect(confirm).toHaveBeenCalledWith("当前有尚未保存的审核修改，确定离开吗？");
    expect(screen.queryByRole("heading", { name: "导出中心" })).toBeNull();
    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: /可导出/ }));
    expect(await screen.findByRole("heading", { name: "导出中心" })).toBeTruthy();
    expect(fetcher).toHaveBeenCalledWith("/api/v1/exports/batches", expect.any(Object));
    await user.click(screen.getByRole("button", { name: "← 返回审核工作台" }));
    expect(within(screen.getByRole("region", { name: "当前审核队列" })).getByText("待复核")).toBeTruthy();
  });
});
