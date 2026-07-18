// @vitest-environment jsdom

import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ExportBatch,
  ExportFilters,
  ExportPreview,
  ExportTask,
} from "@form-detection/api-client";

import { ExportCenter, type ExportCenterApi } from "./ExportCenter_ds";

const preview: ExportPreview = {
  included: [{ form_id: "FORM-1", record_version: 2, reasons: [] }],
  excluded: [{
    form_id: "FORM-2",
    record_version: 1,
    reason: "RULE_BLOCKED",
    reasons: [
      { scope: "FORM", code: "NOT_CONFIRMED", message: "Form is not confirmed." },
      {
        scope: "FIELD",
        code: "NOT_ALLOWED",
        field_key: "shift",
        message: "Value is not in the allowed set.",
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

describe("ExportCenter", () => {
  it("presents export as four business steps and hides technical details until requested", async () => {
    const user = userEvent.setup();
    const api = makeApi();
    render(<ExportCenter api={api} />);

    for (const name of ["选择数据", "检查数据", "生成 Excel", "下载文件"]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
    expect(screen.queryByText("BATCH-OLD")).toBeNull();
    expect(screen.queryByText(/file-sha/)).toBeNull();
    expect(screen.queryByText("payroll-old.xlsx")).toBeNull();

    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));
    expect(await screen.findByRole("heading", { name: "将要导出的记录" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "无法导出的记录及原因" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Excel 列对应关系" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "生成 Excel" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /打开.*追溯详情/ }));
    const trace = await screen.findByRole("complementary", { name: "追溯详情" });
    expect(within(trace).getByText("BATCH-OLD")).toBeTruthy();
    expect(within(trace).getByText("file-sha")).toBeTruthy();
    expect(within(trace).getByText("mapping-hash")).toBeTruthy();
    expect(within(trace).getByText("payroll-old.xlsx")).toBeTruthy();
    expect(within(trace).getByRole("button", { name: "复制追溯信息" })).toBeTruthy();
  });

  it("defaults preview and ordinary create to NOT_EXPORTED without an ALL bypass", async () => {
    const user = userEvent.setup();
    const api = makeApi();
    render(<ExportCenter api={api} />);

    const status = screen.getByLabelText("导出状态") as HTMLSelectElement;
    expect(status.value).toBe("NOT_EXPORTED");
    expect(within(status).queryByRole("option", { name: "全部" })).toBeNull();
    await user.type(screen.getByLabelText("表单编号"), "FORM-1");
    await user.clear(screen.getByLabelText("表单编号"));
    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));

    expect(api.preview).toHaveBeenCalledWith(
      expect.objectContaining({ export_status: "NOT_EXPORTED" }),
      expect.anything(),
    );
    await user.click(await screen.findByRole("button", { name: "生成 Excel" }));
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
    render(<ExportCenter api={api} />);

    await user.type(screen.getByLabelText("表单编号"), "FORM/一");
    await user.type(screen.getByLabelText("员工编号"), "E&01");
    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));

    expect(api.preview).toHaveBeenCalledWith(
      expect.objectContaining({ form_id: "FORM/一", employee_id: "E&01" }),
      expect.anything(),
    );
    expect(await screen.findByText("FORM-1 · 记录版本 2")).toBeTruthy();
    const excluded = screen.getByRole("region", { name: "无法导出的记录" });
    expect(within(excluded).getByText("FORM-2 · 记录版本 1")).toBeTruthy();
    expect(within(excluded).getByText("整张表单")).toBeTruthy();
    expect(within(excluded).getByText("表单尚未完成确认。")).toBeTruthy();
    expect(within(excluded).queryByText("Form is not confirmed.")).toBeNull();
    expect(within(excluded).getByText("字段 shift")).toBeTruthy();
    expect(within(excluded).getByText("填写内容不在模板允许范围内。")).toBeTruthy();
    expect(within(excluded).getByText("必填；允许值：A、B；范围：1–10")).toBeTruthy();
    expect(within(excluded).queryByText("RULE_BLOCKED")).toBeNull();
    expect(screen.getByText("企业工资记录.xlsx / 计时考核单 / employee_id")).toBeTruthy();
  });

  it("discards an aborted stale preview and creates only from the latest filter snapshot", async () => {
    const user = userEvent.setup();
    const first = deferred<ExportPreview>();
    const second = deferred<ExportPreview>();
    let firstSignal: AbortSignal | undefined;
    const previewRequest = vi.fn()
      .mockImplementationOnce((_filters: ExportFilters, signal?: AbortSignal) => {
        firstSignal = signal;
        return first.promise;
      })
      .mockImplementationOnce((_filters: ExportFilters, _signal?: AbortSignal) => second.promise);
    const api = makeApi({ preview: previewRequest });
    render(<ExportCenter api={api} />);

    const formId = screen.getByLabelText("表单编号");
    await user.type(formId, "FORM-A");
    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));
    await waitFor(() => expect(previewRequest).toHaveBeenCalledTimes(1));
    await user.clear(formId);
    await user.type(formId, "FORM-B");
    expect(firstSignal?.aborted).toBe(true);
    await act(async () => first.resolve({
      ...preview,
      included: [{ form_id: "FORM-A", record_version: 1, reasons: [] }],
    }));

    expect(screen.queryByText("FORM-A · 记录版本 1")).toBeNull();
    expect(screen.queryByRole("button", { name: "生成 Excel" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));
    await waitFor(() => expect(previewRequest).toHaveBeenCalledTimes(2));
    await act(async () => second.resolve({
      ...preview,
      included: [{ form_id: "FORM-B", record_version: 2, reasons: [] }],
    }));
    await user.click(await screen.findByRole("button", { name: "生成 Excel" }));

    await waitFor(() => expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({
          form_id: "FORM-B",
          export_status: "NOT_EXPORTED",
        }),
      }),
      expect.any(String),
    ));
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
    render(<ExportCenter api={api} />);

    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));
    await user.click(await screen.findByRole("button", { name: "生成 Excel" }));

    expect(await screen.findByText("正在写入工作表")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("55");
    await act(async () => { finishTask(succeededTask); });
    expect(await screen.findByText("导出任务已完成。" )).toBeTruthy();
    expect(api.listBatches).toHaveBeenCalledTimes(2);

    const history = screen.getByRole("region", { name: "导出批次历史" });
    expect(within(history).getByText("导出记录 OLD")).toBeTruthy();
    await user.click(within(history).getByRole("button", { name: "下载文件" }));
    await waitFor(() => expect(api.downloadBatch).toHaveBeenCalledWith("BATCH-OLD"));
    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
  });

  it("shows REEXPORT_REQUIRED and submits the actual source batch as supersedes_batch_id", async () => {
    const user = userEvent.setup();
    const api = makeApi();
    render(<ExportCenter api={api} />);

    await user.selectOptions(screen.getByLabelText("导出状态"), "REEXPORT_REQUIRED");
    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));

    expect((await screen.findByRole("alert")).textContent).toContain("记录在上次导出后发生修改");
    const ordinaryCreate = screen.getByRole("button", { name: "生成 Excel" });
    expect(ordinaryCreate.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("重导必须从下方选择一个覆盖全部表单旧版本的来源批次。")).toBeTruthy();
    await user.click(ordinaryCreate);
    expect(api.create).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "用此记录生成修正版" }));

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
    render(<ExportCenter api={api} />);

    await user.selectOptions(screen.getByLabelText("导出状态"), "REEXPORT_REQUIRED");
    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));

    expect(screen.queryByRole("button", { name: "用此记录生成修正版" })).toBeNull();
    const disabledSource = screen.getByRole("button", { name: "此记录不可用于重导" });
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
    const rendered = render(<ExportCenter api={api} />);

    await waitFor(() => expect(api.listBatches).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));
    await user.click(await screen.findByRole("button", { name: "生成 Excel" }));
    await waitFor(() => expect(waitForTask).toHaveBeenCalledTimes(1));
    rendered.unmount();

    expect(pollingSignal).toBeDefined();
    expect(pollingSignal?.aborted).toBe(true);
    await Promise.resolve();
    expect(api.listBatches).toHaveBeenCalledTimes(1);
  });

  it("keeps the newest batch refresh when an older list request resolves last", async () => {
    const user = userEvent.setup();
    const initial = deferred<ExportBatch[]>();
    const refreshed = deferred<ExportBatch[]>();
    const newBatch: ExportBatch = {
      ...oldBatch,
      export_batch_id: "BATCH-NEW",
      task_id: "TASK-NEW",
      download_name: "payroll-new.xlsx",
    };
    const listBatches = vi.fn()
      .mockImplementationOnce(() => initial.promise)
      .mockImplementationOnce(() => refreshed.promise);
    const api = makeApi({ listBatches });
    render(<ExportCenter api={api} />);

    await waitFor(() => expect(listBatches).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "检查可导出的数据" }));
    await user.click(await screen.findByRole("button", { name: "生成 Excel" }));
    await waitFor(() => expect(listBatches).toHaveBeenCalledTimes(2));
    await act(async () => refreshed.resolve([newBatch]));
    expect(await screen.findByText("导出记录 NEW")).toBeTruthy();
    await act(async () => initial.resolve([oldBatch]));

    expect(screen.getByText("导出记录 NEW")).toBeTruthy();
    expect(screen.queryByText("导出记录 OLD")).toBeNull();
  });

});
