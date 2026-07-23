// @vitest-environment jsdom

import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import type { BambooRecord, MobileApiClient, MobileSession } from "@form-detection/api-client";

const mocks = vi.hoisted(() => ({
  getBambooDashboard: vi.fn(),
  listBambooTasks: vi.fn(),
  getBambooRecord: vi.fn(),
  getBambooRecordOptions: vi.fn(),
  createBambooRecord: vi.fn(),
  submitBambooStage: vi.fn(),
  getBambooOperations: vi.fn(),
  listBambooInspectionQueue: vi.fn(),
  claimBambooInspection: vi.fn(),
  submitBambooInspection: vi.fn(),
  listBambooNotifications: vi.fn(),
  listBambooHistory: vi.fn(),
  listBambooRoleOptions: vi.fn(),
  listBambooFactoryEmployees: vi.fn(),
  listBambooRoleChanges: vi.fn(),
  listBambooFactories: vi.fn(),
  listBambooPersonnelTransfers: vi.fn(),
  createBambooPersonnelTransfer: vi.fn(),
  decideBambooPersonnelTransferAsManager: vi.fn(),
  executeBambooPersonnelTransfer: vi.fn(),
  createBambooFactoryEmployee: vi.fn(),
}));

vi.mock("@form-detection/api-client", async (importOriginal) => ({
  ...await importOriginal<typeof import("@form-detection/api-client")>(),
  mobileApiClient: {
    getBambooDashboard: mocks.getBambooDashboard,
    listBambooTasks: mocks.listBambooTasks,
    getBambooRecord: mocks.getBambooRecord,
    getBambooRecordOptions: mocks.getBambooRecordOptions,
    createBambooRecord: mocks.createBambooRecord,
    submitBambooStage: mocks.submitBambooStage,
    getBambooOperations: mocks.getBambooOperations,
    listBambooInspectionQueue: mocks.listBambooInspectionQueue,
    claimBambooInspection: mocks.claimBambooInspection,
    submitBambooInspection: mocks.submitBambooInspection,
    listBambooNotifications: mocks.listBambooNotifications,
    listBambooHistory: mocks.listBambooHistory,
    listBambooRoleOptions: mocks.listBambooRoleOptions,
    listBambooFactoryEmployees: mocks.listBambooFactoryEmployees,
    listBambooRoleChanges: mocks.listBambooRoleChanges,
    listBambooFactories: mocks.listBambooFactories,
    listBambooPersonnelTransfers: mocks.listBambooPersonnelTransfers,
    createBambooPersonnelTransfer: mocks.createBambooPersonnelTransfer,
    decideBambooPersonnelTransferAsManager: mocks.decideBambooPersonnelTransferAsManager,
    executeBambooPersonnelTransfer: mocks.executeBambooPersonnelTransfer,
    createBambooFactoryEmployee: mocks.createBambooFactoryEmployee,
  },
}));
vi.mock("../device", () => ({ createMobileClientId: (prefix: string) => `${prefix}-key`, getMobileDeviceId: () => "device-v3" }));

import { BambooRecordDetailPage } from "../bamboo/BambooRecordDetailPage";
import { BambooTaskListPage } from "../bamboo/BambooTaskListPage";
import { BambooPersonnelPage } from "../personnel/BambooPersonnelPage";
import { MobileSessionProvider } from "../session/MobileSessionProvider";
import { BambooV3ProfilePage } from "./BambooV3ProfilePage";
import { BambooV3SubmissionsPage } from "./BambooV3SubmissionsPage";

const worker: MobileSession = {
  employee_name: "王分选",
  employee_code: "ZS001",
  team_name: "竹丝生产组",
  position: "分选工",
  roles: ["WORKER"],
  allowed_form_types: [],
  allowed_processes: ["BAMBOO_PROCESS"],
  factory_id: "FACTORY-A",
  factory_name: "竹丝示范一厂",
  bamboo_role: "SORT_OPERATOR",
};

const sortingRecord: BambooRecord = {
  record_id: "SORT-18",
  display_no: "FX-20260722-018",
  factory_id: "FACTORY-A",
  source_type: "MOBILE_CREATED",
  source_ref: "create-18",
  form_type: "SORTING",
  production_object_id: "CAGE-18",
  source_record_id: null,
  source_snapshot: {},
  base_info: { mode: "分选+装笼", cage_no: "3-018", length: "2.3", grade: "A", bundle_count: 16 },
  current_stage: "SUPERVISOR",
  status: "ACTIVE",
  revision: 2,
  created_by: "ZS001",
  created_at: "2026-07-22T02:30:00Z",
  updated_at: "2026-07-22T04:30:00Z",
  upstream_record: null,
  submissions: [
    { submission_id: "SORT-S1", stage: "SORT", version: 1, values: { moisture: [12, 13] }, actor_id: "1", actor_name: "王分选", role_code: "SORT_OPERATOR", submitted_at: "2026-07-22T03:00:00Z" },
  ],
};

const jointRecord: BambooRecord = {
  ...sortingRecord,
  record_id: "JOINT-18",
  display_no: "JG-20260722-018",
  source_type: "SORTING_RECORD",
  source_ref: sortingRecord.display_no,
  form_type: "DIPPING_DRYING",
  source_record_id: sortingRecord.record_id,
  source_snapshot: {
    record_id: sortingRecord.record_id,
    display_no: sortingRecord.display_no,
    revision: 2,
    original_revision: 2,
    latest_revision: 3,
    source_status: "UPSTREAM_CHANGED",
    base_info: sortingRecord.base_info,
  },
  upstream_record: {
    record_id: sortingRecord.record_id,
    display_no: sortingRecord.display_no,
    factory_id: sortingRecord.factory_id,
    form_type: sortingRecord.form_type,
    base_info: sortingRecord.base_info,
    current_stage: sortingRecord.current_stage,
    status: sortingRecord.status,
    revision: sortingRecord.revision,
    submissions: sortingRecord.submissions,
  },
  current_stage: "SUPERVISOR",
  revision: 3,
  submissions: [
    { submission_id: "DIP-S1", stage: "DIPPING", version: 1, values: { glue_batch: "J-01", moisture: [11] }, actor_id: "2", actor_name: "李浸胶", role_code: "DIPPING_OPERATOR", submitted_at: "2026-07-22T03:30:00Z" },
    { submission_id: "DRY-S1", stage: "DRYING", version: 1, values: { rack_numbers: ["G-01"], moisture: [9] }, actor_id: "3", actor_name: "陈干燥", role_code: "DRYING_RACK_OPERATOR", submitted_at: "2026-07-22T04:00:00Z" },
  ],
};

const presets = {
  options_version: "factory-sort-v1",
  special_classes: ["直装", "防霉"],
  lengths: ["2.1", "2.3", "2.5"],
  shades: ["深", "浅"],
  grades: ["A", "B"],
  weight_factors: { "2.1": "5", "2.3": "6", "2.5": "7" },
};

function client(session: MobileSession): MobileApiClient {
  return { getSession: vi.fn().mockResolvedValue(session), login: vi.fn(), logout: vi.fn() } as unknown as MobileApiClient;
}

function withSession(ui: React.ReactNode, session: MobileSession = worker) {
  return render(<MemoryRouter><MobileSessionProvider client={client(session)}>{ui}</MobileSessionProvider></MemoryRouter>);
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  localStorage.clear();
  mocks.getBambooDashboard.mockResolvedValue({ available: 2, waiting: 0, completed: 0 });
  mocks.listBambooTasks.mockResolvedValue({ bucket: "available", tasks: [sortingRecord, jointRecord] });
  mocks.getBambooRecord.mockResolvedValue(sortingRecord);
  mocks.getBambooRecordOptions.mockResolvedValue(presets);
  mocks.createBambooRecord.mockResolvedValue({ ...sortingRecord, current_stage: "SORT", revision: 1, submissions: [] });
  mocks.submitBambooStage.mockResolvedValue(sortingRecord);
  mocks.getBambooOperations.mockResolvedValue({ payroll_facts: [], inspections: [], corrections: [] });
  mocks.listBambooInspectionQueue.mockImplementation((bucket: string) => Promise.resolve({
    bucket,
    items: bucket === "active" ? [{
      record_id: "SORT-18", display_no: "FX-20260722-018", form_type: "SORTING",
      cage_no: "3-018", status: "CLAIMED", opened_at: "2026-07-22T04:30:00Z",
      deadline_at: "2099-07-22T06:30:00Z", inside_window: true, claimed_by: "ZS001",
      claimed_at: "2026-07-22T04:31:00Z", completed_at: null,
      appeal_deadline_at: null, appeal_claimed_by: null, appeal_submitted_at: null,
      appeal_decision: null, revision: 2,
    }] : [],
  }));
  mocks.claimBambooInspection.mockResolvedValue({});
  mocks.submitBambooInspection.mockResolvedValue({ inspection_id: "I-1", evidence: [] });
  mocks.listBambooNotifications.mockResolvedValue({ items: [] });
  mocks.listBambooHistory.mockResolvedValue([
    { activity_id: "SUB-1", record_id: "SORT-18", display_no: "FX-20260722-018", form_type: "SORTING", cage_no: "3-018", action: "SORT", submitted_at: "2026-07-22T04:00:00Z", current_stage: "SUPERVISOR", status: "ACTIVE" },
  ]);
  mocks.listBambooRoleOptions.mockResolvedValue([
    { role_code: "DIPPING_OPERATOR", display_name: "浸胶工", category: "PRODUCTION", self_requestable: true },
  ]);
  mocks.listBambooFactoryEmployees.mockResolvedValue([]);
  mocks.listBambooRoleChanges.mockResolvedValue([]);
  mocks.listBambooFactories.mockResolvedValue([
    { factory_id: "FACTORY-A", code: "A", name: "竹丝示范一厂" },
    { factory_id: "FACTORY-B", code: "B", name: "竹丝二厂" },
  ]);
  mocks.listBambooPersonnelTransfers.mockResolvedValue([]);
  mocks.createBambooPersonnelTransfer.mockResolvedValue({});
  mocks.decideBambooPersonnelTransferAsManager.mockResolvedValue({});
  mocks.executeBambooPersonnelTransfer.mockResolvedValue({});
  mocks.createBambooFactoryEmployee.mockResolvedValue({ employee_code: "ZS009" });
});

afterEach(cleanup);

describe("independent bamboo forms", () => {
  it("lists SORTING and DIPPING_DRYING as separate records", async () => {
    withSession(<BambooTaskListPage />);
    expect(await screen.findByText(sortingRecord.display_no)).toBeTruthy();
    expect(screen.getByText(jointRecord.display_no)).toBeTruthy();
    expect(screen.getAllByText(/分选表/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/浸胶\+干燥联合表/).length).toBeGreaterThan(0);
  });

  it("requires dipping workers to search an upstream cage before showing work", async () => {
    const user = userEvent.setup();
    withSession(<BambooTaskListPage />, { ...worker, bamboo_role: "DIPPING_OPERATOR", position: "浸胶工" });
    expect(await screen.findByRole("heading", { name: "请先搜索笼号" })).toBeTruthy();
    expect(mocks.listBambooTasks).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("按笼号查找上游表单"), "3-018");
    await user.click(screen.getByRole("button", { name: "搜索" }));
    await waitFor(() => expect(mocks.listBambooTasks).toHaveBeenCalledWith("available", "3-018"));
    expect(await screen.findByText(jointRecord.display_no)).toBeTruthy();
  });

  it("creates a fixed SORTING record then submits SORT with moisture", async () => {
    const user = userEvent.setup();
    withSession(<BambooTaskListPage />);

    await user.click(await screen.findByRole("button", { name: "新建竹丝记录" }));
    await user.click(await screen.findByRole("button", { name: "分选+装笼" }));
    await user.click(screen.getByRole("button", { name: /点开选择长度/ }));
    await user.click(await screen.findByRole("button", { name: "2.3" }));
    await user.click(screen.getByRole("button", { name: /点开选择深浅/ }));
    await user.click(await screen.findByRole("button", { name: "深" }));
    await user.click(screen.getByRole("button", { name: /点开选择品级/ }));
    await user.click(await screen.findByRole("button", { name: "A" }));
    await user.type(screen.getByLabelText(/笼号/), "L-207");
    await user.type(screen.getByLabelText(/把数/), "12");
    await user.type(screen.getByText("检测点 1").closest("label")!.querySelector("input")!, "12");
    await user.type(screen.getByText("检测点 2").closest("label")!.querySelector("input")!, "14");
    await user.click(screen.getByRole("button", { name: "核对并提交分选/装笼记录" }));
    expect(await screen.findByText("确认后将建立分选表并绑定当前身份完成分选签字。")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "确认提交" }));

    await waitFor(() => expect(mocks.createBambooRecord).toHaveBeenCalledWith(
      expect.objectContaining({ mode: "分选+装笼", length: "2.3", cage_no: "L-207", bundle_count: 12, options_version: "factory-sort-v1" }),
      "sorting-record-key",
    ));
    expect(mocks.submitBambooStage).toHaveBeenCalledWith(
      "SORT-18",
      "SORT",
      { expected_revision: 1, device_id: "device-v3", values: { moisture: [12, 14] } },
      "sorting-stage-key",
    );
  });

  it("blocks creation when presets fail and enables it after retry", async () => {
    const user = userEvent.setup();
    mocks.getBambooRecordOptions.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(presets);
    withSession(<BambooTaskListPage />);

    await user.click(await screen.findByRole("button", { name: "新建竹丝记录" }));
    expect((await screen.findByRole("alert")).textContent).toContain("后台发布选项加载失败");
    expect((screen.getByRole("button", { name: "核对并提交分选/装笼记录" }) as HTMLButtonElement).disabled).toBe(true);
    expect(mocks.createBambooRecord).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "重新加载" }));
    await waitFor(() => expect((screen.getByRole("button", { name: /点开选择长度/ }) as HTMLButtonElement).disabled).toBe(false));
    expect(mocks.getBambooRecordOptions).toHaveBeenCalledTimes(2);
  });

  it("restores only a pending submission owned by the same employee, factory and device", async () => {
    const key = "bamboo-v3-pending-sorting-submission:ZS001:FACTORY-A:device-v3";
    sessionStorage.setItem(key, JSON.stringify({
      ownerEmployeeCode: "ZS001", factoryId: "FACTORY-A", deviceId: "device-v3",
      createKey: "create-pending", stageKey: "stage-pending",
      draft: { mode: "分选", special_classes: [], length: "2.3", shade: "深", grade: "A", supplier: "", cage_no: "L-9", bundle_count: "9" },
      moisture: ["12"], baseInfo: { mode: "分选", length: "2.3", cage_no: "L-9", bundle_count: 9 },
    }));
    withSession(<BambooTaskListPage />);
    expect(await screen.findByRole("button", { name: "继续未完成的分选提交" })).toBeTruthy();
    expect(screen.getAllByText(/属于当前账号、工厂和设备的未完成分选提交/).length).toBeGreaterThan(0);
    cleanup();

    withSession(<BambooTaskListPage />, { ...worker, employee_code: "OTHER" });
    expect(await screen.findByRole("button", { name: "新建竹丝记录" })).toBeTruthy();
    expect(screen.queryByText(/属于当前账号、工厂和设备的未完成分选提交/)).toBeNull();
  });

  it("shows only the sorting approval flow on a SORTING record", async () => {
    withSession(<BambooRecordDetailPage recordId="SORT-18" />, { ...worker, bamboo_role: "SUPERVISOR", position: "主管" });
    expect(await screen.findByRole("heading", { name: "分选表详情" })).toBeTruthy();
    const flow = screen.getByRole("list", { name: "分选表表内进度" });
    expect(within(flow).getAllByRole("listitem").map((item) => item.querySelector("span")?.textContent)).toEqual(["分选签字", "主管审核", "厂长审核", "已生效"]);
    expect(within(flow).queryByText("浸胶记录")).toBeNull();
    expect(within(flow).queryByText("干燥联合签字")).toBeNull();
  });

  it("shows source version, upstream warning and joint flow on DIPPING_DRYING", async () => {
    mocks.getBambooRecord.mockResolvedValue(jointRecord);
    withSession(<BambooRecordDetailPage recordId="JOINT-18" />, { ...worker, bamboo_role: "SUPERVISOR", position: "主管" });
    expect(await screen.findByRole("heading", { name: "浸胶+干燥联合表详情" })).toBeTruthy();
    expect(screen.getByText("上游数据已变更，待主管确认")).toBeTruthy();
    const sourceCard = screen.getByRole("heading", { name: "来源分选表" }).closest("section")!;
    expect(sourceCard.querySelector("p")?.textContent).toBe(`${sortingRecord.display_no} · 第 2 版`);
    expect(screen.queryByRole("link", { name: "查看上游分选表" })).toBeNull();
    expect(sourceCard.querySelector("details")).toBeTruthy();
    expect(sourceCard.textContent).toContain("12");
    const flow = screen.getByRole("list", { name: "浸胶+干燥联合表表内进度" });
    expect(within(flow).getAllByRole("listitem").map((item) => item.querySelector("span")?.textContent)).toEqual(["浸胶记录", "干燥联合签字", "主管审核", "厂长审核", "已生效"]);
  });

  it("limits inspector and supervisor targets by form type", async () => {
    mocks.getBambooRecord.mockResolvedValue({ ...sortingRecord, current_stage: "PLANT_AUDIT", revision: 3 });
    withSession(<BambooRecordDetailPage recordId="SORT-18" />, { ...worker, bamboo_role: "INSPECTOR", position: "检测人" });
    await userEvent.setup().click(await screen.findByRole("button", { name: "报告异常" }));
    expect(await screen.findByLabelText("检测目标")).toBeTruthy();
    expect(Array.from((screen.getByLabelText("检测目标") as HTMLSelectElement).options).map((item) => item.text)).toEqual(["分选"]);
    cleanup();

    mocks.getBambooRecord.mockResolvedValue(jointRecord);
    withSession(<BambooRecordDetailPage recordId="JOINT-18" />, { ...worker, bamboo_role: "SUPERVISOR", position: "主管" });
    expect(await screen.findByRole("heading", { name: "主管处理" })).toBeTruthy();
    expect(screen.queryByLabelText("浸胶")).toBeNull();
    await userEvent.setup().click(screen.getByRole("button", { name: "发现问题，发起回退" }));
    const returnSection = screen.getByRole("heading", { name: "主管处理" }).closest("section")!;
    expect(within(returnSection).getByLabelText("浸胶")).toBeTruthy();
    expect(within(returnSection).getByLabelText("干燥")).toBeTruthy();
    expect(within(returnSection).queryByLabelText("分选")).toBeNull();
  });

  it("shows the two-hour queue and explicit Android capture controls", async () => {
    mocks.getBambooRecord.mockResolvedValue({ ...sortingRecord, current_stage: "PLANT_AUDIT", revision: 3 });
    const user = userEvent.setup();
    withSession(<BambooRecordDetailPage recordId="SORT-18" />, { ...worker, bamboo_role: "INSPECTOR", position: "检测人" });
    expect(await screen.findByText(/检测剩余时间/)).toBeTruthy();
    expect(screen.getByLabelText("搜索表号或笼号")).toBeTruthy();
    expect(screen.getByText("3-018")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "检测合格" }));
    await waitFor(() => expect(mocks.submitBambooInspection).toHaveBeenCalledWith(
      "SORT-18",
      expect.objectContaining({ conclusion: "CONFORMING" }),
      "inspection-key",
    ));
    await user.click(screen.getByRole("button", { name: "报告异常" }));
    expect(screen.getByRole("button", { name: "点击拍照" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "点击录音" })).toBeTruthy();
    expect(screen.queryByLabelText("检测序号")).toBeNull();
  });
});

describe("V3 submissions and profile", () => {
  it("shows bamboo signing history and automatic draft count", async () => {
    localStorage.setItem("bamboo-v3-draft:ZS001:FACTORY-A:device-v3:SORT-18:SORT", "{}");
    withSession(<BambooV3SubmissionsPage />);
    expect(screen.getByRole("heading", { name: "历史记录" })).toBeTruthy();
    expect(await screen.findByText("FX-20260722-018")).toBeTruthy();
    expect(screen.getByText("自动保存草稿").previousElementSibling?.textContent).toBe("1");
    expect(screen.getByText(/分选签字/)).toBeTruthy();
  });

  it("does not expose worker self-service role changes", async () => {
    withSession(<BambooV3ProfilePage />);
    expect(await screen.findByRole("heading", { name: "我的" })).toBeTruthy();
    expect(screen.getByText("竹丝示范一厂")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "申请换岗" })).toBeNull();
    expect(screen.getByText(/员工端不提供自行申请入口/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /财务审批/ })).toBeNull();
  });

  it("gives managers an independent responsive personnel workspace", async () => {
    mocks.listBambooFactoryEmployees.mockResolvedValue([
      { employee_code: "ZS001", employee_name: "王分选", factory_id: "FACTORY-A", role_code: "SORT_OPERATOR", role_name: "分选工" },
    ]);
    mocks.listBambooRoleOptions.mockResolvedValue([
      { role_code: "DIPPING_OPERATOR", display_name: "浸胶工", category: "PRODUCTION", self_requestable: false },
    ]);
    withSession(<BambooPersonnelPage />, { ...worker, bamboo_role: "PLANT_MANAGER", position: "厂长" });

    expect(await screen.findByRole("heading", { name: "人员调度中心" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "发起人员调动" })).toBeTruthy();
    expect(await screen.findByRole("option", { name: /王分选/ })).toBeTruthy();
    expect(screen.getByRole("option", { name: "竹丝二厂" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "申请换岗" })).toBeNull();
  });

  it("keeps new employee enrollment in the manager workspace", async () => {
    mocks.listBambooRoleOptions.mockResolvedValue([
      { role_code: "SORT_OPERATOR", display_name: "分选工", category: "PRODUCTION", self_requestable: false },
    ]);
    withSession(<BambooPersonnelPage />, { ...worker, bamboo_role: "PLANT_MANAGER", position: "厂长" });

    expect(await screen.findByRole("heading", { name: "添加本厂新员工" })).toBeTruthy();
    expect(screen.getByLabelText("员工姓名")).toBeTruthy();
    expect(screen.getByRole("button", { name: "添加到本厂" })).toBeTruthy();
  });
});
