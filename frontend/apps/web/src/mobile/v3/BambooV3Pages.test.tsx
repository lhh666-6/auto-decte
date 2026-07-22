// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
  getBambooOperations: vi.fn(),
  listSubmissions: vi.fn(),
  listDrafts: vi.fn(),
  countAll: vi.fn(),
  listBambooRoleChanges: vi.fn(),
}));

vi.mock("@form-detection/api-client", async (importOriginal) => ({
  ...await importOriginal<typeof import("@form-detection/api-client")>(),
  mobileApiClient: {
    getBambooDashboard: mocks.getBambooDashboard,
    listBambooTasks: mocks.listBambooTasks,
    getBambooRecord: mocks.getBambooRecord,
    getBambooRecordOptions: mocks.getBambooRecordOptions,
    createBambooRecord: mocks.createBambooRecord,
    getBambooOperations: mocks.getBambooOperations,
    listSubmissions: mocks.listSubmissions,
    listBambooRoleChanges: mocks.listBambooRoleChanges,
  },
}));
vi.mock("../storage/drafts", () => ({ listDrafts: mocks.listDrafts }));
vi.mock("../storage/outbox", () => ({ countAll: mocks.countAll }));
vi.mock("../device", () => ({ createMobileClientId: () => "record-key", getMobileDeviceId: () => "device-v3" }));

import { BambooRecordDetailPage } from "../bamboo/BambooRecordDetailPage";
import { BambooTaskListPage } from "../bamboo/BambooTaskListPage";
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

const record: BambooRecord = {
  record_id: "BR-18",
  display_no: "ZS-20260722-018",
  factory_id: "FACTORY-A",
  source_type: "MOBILE_CREATED",
  source_ref: "create-18",
  base_info: { cage_no: "3-018", length: "2.3", grade: "A", bundle_count: 16 },
  current_stage: "SUPERVISOR",
  status: "ACTIVE",
  revision: 4,
  created_by: "ZS001",
  created_at: "2026-07-22T02:30:00Z",
  updated_at: "2026-07-22T04:30:00Z",
  submissions: [
    { submission_id: "S1", stage: "SORT", version: 1, values: { sort_quantity: 16, wage_amount: 80 }, actor_id: "1", actor_name: "王分选", role_code: "SORT_OPERATOR", submitted_at: "2026-07-22T03:00:00Z" },
    { submission_id: "S2", stage: "DIPPING", version: 1, values: { glue_batch: "J-01" }, actor_id: "2", actor_name: "李浸胶", role_code: "DIPPING_OPERATOR", submitted_at: "2026-07-22T03:30:00Z" },
    { submission_id: "S3", stage: "DRYING", version: 1, values: { rack_no: "G-01" }, actor_id: "3", actor_name: "陈干燥", role_code: "DRYING_RACK_OPERATOR", submitted_at: "2026-07-22T04:00:00Z" },
  ],
};

function client(session: MobileSession): MobileApiClient {
  return { getSession: vi.fn().mockResolvedValue(session), login: vi.fn(), logout: vi.fn() } as unknown as MobileApiClient;
}

function withSession(ui: React.ReactNode, session: MobileSession = worker) {
  return render(<MemoryRouter><MobileSessionProvider client={client(session)}>{ui}</MobileSessionProvider></MemoryRouter>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getBambooDashboard.mockResolvedValue({ available: 1, waiting: 2, completed: 3 });
  mocks.listBambooTasks.mockResolvedValue({ bucket: "available", tasks: [record] });
  mocks.getBambooRecord.mockResolvedValue(record);
  mocks.getBambooRecordOptions.mockResolvedValue({
    options_version: "factory-sort-v1",
    special_classes: ["直装", "防霉"],
    lengths: ["2.1", "2.3", "2.5"],
    shades: ["深", "浅"],
    grades: ["A", "B"],
    weight_factors: { "2.1": "5", "2.3": "6", "2.5": "7" },
  });
  mocks.createBambooRecord.mockResolvedValue(record);
  mocks.getBambooOperations.mockResolvedValue({ payroll_facts: [], inspections: [], corrections: [] });
  mocks.listSubmissions.mockResolvedValue({ submissions: [
    { submission_id: "SUB-1", form_id: "ZS-18", subject_employee_code: "ZS001", status: "ACCEPTED", submitted_at: "2026-07-22T04:00:00Z", idempotency_key: "key" },
  ] });
  mocks.listDrafts.mockResolvedValue([{ storageKey: "draft-1" }]);
  mocks.countAll.mockResolvedValue(2);
  mocks.listBambooRoleChanges.mockResolvedValue([{ request_id: "RC-1", employee_code: "JZ001", from_role: "DIPPING_OPERATOR", to_role: "DRYING_RACK_OPERATOR", reason: "调整班组", status: "PENDING" }]);
});

afterEach(cleanup);

describe("V3 work and record pages", () => {
  it("uses the only work list with the three V3 buckets and V3 record links", async () => {
    withSession(<BambooTaskListPage />);
    expect(await screen.findByRole("heading", { name: "记录工作" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /可记录/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /等待上游/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /已完成/ })).toBeTruthy();
    expect((await screen.findByText(record.display_no)).closest("a")?.getAttribute("href")).toBe("/mobile/records/BR-18");
  });

  it("creates a sort record with published picker options and a visible confirmation", async () => {
    const user = userEvent.setup();
    withSession(<BambooTaskListPage />);

    await user.click(await screen.findByRole("button", { name: "新建竹丝记录" }));
    expect(await screen.findByRole("dialog", { name: "新建竹丝记录" })).toBeTruthy();
    expect(screen.getByText("预设选项由管理员后台发布；手机端只能点选，不能临时新增。")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /点开选择长度/ }));
    await user.click(await screen.findByRole("button", { name: "2.3" }));
    await user.click(screen.getByRole("button", { name: /点开选择深浅/ }));
    await user.click(await screen.findByRole("button", { name: "深" }));
    await user.click(screen.getByRole("button", { name: /点开选择品级/ }));
    await user.click(await screen.findByRole("button", { name: "A" }));
    await user.type(screen.getByLabelText(/笼号/), "L-207");
    await user.type(screen.getByLabelText(/把数/), "12");
    expect(screen.getByText(/12 把 × 6/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "核对并建立" }));
    expect(screen.getByRole("dialog", { name: "确认建立竹丝记录" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "确认建立" }));

    await waitFor(() => expect(mocks.createBambooRecord).toHaveBeenCalledWith(
      expect.objectContaining({
        length: "2.3",
        shade: "深",
        grade: "A",
        cage_no: "L-207",
        bundle_count: 12,
        options_version: "factory-sort-v1",
      }),
      "record-key",
    ));
  });

  it("shows supervisors the opened whole electronic form and locks downstream stages", async () => {
    withSession(<BambooRecordDetailPage recordId="BR-18" />, { ...worker, bamboo_role: "SUPERVISOR", position: "主管" });
    expect(await screen.findByRole("heading", { name: "竹丝流程详情" })).toBeTruthy();
    expect(screen.getByText("整张电子表单")).toBeTruthy();
    expect(screen.getByText("分选记录")).toBeTruthy();
    expect(screen.getByText("浸胶与干燥联合作业")).toBeTruthy();
    expect(screen.getByText("厂长审核").closest("li")?.textContent).toContain("前序完成后开放");
    expect(screen.getByText("分选签字后工资已确定")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "主管选择性回退" })).toBeTruthy();
    expect(screen.getByText("只勾选确实需要重写的工序，系统会自动作废其下游签字，旧版本仍保留用于审计。")).toBeTruthy();
    expect(screen.queryByText("财务逐条审批")).toBeNull();
  });

  it("gives inspectors a self-chosen serial, first-three-stage selector and three evidence modes", async () => {
    withSession(<BambooRecordDetailPage recordId="BR-18" />, { ...worker, bamboo_role: "INSPECTOR", position: "检测人" });
    expect(await screen.findByLabelText("检测序号")).toBeTruthy();
    const stageSelect = screen.getByLabelText("检测流程");
    expect(Array.from((stageSelect as HTMLSelectElement).options).map((option) => option.text)).toEqual(["分选", "浸胶", "干燥"]);
    expect(screen.getByLabelText("文字留痕")).toBeTruthy();
    expect(screen.getByLabelText("照片或录音").getAttribute("accept")).toBe("image/*,audio/*");
  });
});

describe("V3 submissions and profile", () => {
  it("merges personal records, drafts and pending sync on one page", async () => {
    withSession(<BambooV3SubmissionsPage />);
    expect(screen.getByRole("heading", { name: "提交记录" })).toBeTruthy();
    await waitFor(() => expect(screen.getByText("本地草稿").nextElementSibling?.textContent).toBe("1"));
    expect(screen.getByText("待同步").nextElementSibling?.textContent).toBe("2");
    expect(screen.getByText("SUB-1")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /草稿/ })).toBeNull();
  });

  it("shows extensible identity controls and no finance approval action", async () => {
    withSession(<BambooV3ProfilePage />);
    expect(await screen.findByRole("heading", { name: "我的" })).toBeTruthy();
    expect(screen.getByText("竹丝示范一厂")).toBeTruthy();
    expect(screen.getByText("分选工")).toBeTruthy();
    expect(screen.getByRole("button", { name: "申请换岗" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "退出登录" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /财务审批/ })).toBeNull();
  });

  it("lets a plant manager configure future roles and review pending applications", async () => {
    withSession(<BambooV3ProfilePage />, { ...worker, employee_name: "钱厂长", employee_code: "CZ001", position: "厂长", bamboo_role: "PLANT_MANAGER" });
    const button = await screen.findByRole("button", { name: "人员与职务配置" });
    await button.click();
    expect(await screen.findByText(/JZ001/)).toBeTruthy();
    expect(screen.getByLabelText("职务代码").getAttribute("list")).toBe("manager-role-options");
    expect(screen.getByText("可输入新增员工和未来职务代码，不限于当前选项。")).toBeTruthy();
  });
});
