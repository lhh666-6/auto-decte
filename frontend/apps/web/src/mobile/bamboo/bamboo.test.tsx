// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import type { BambooRecord, MobileApiClient } from "@form-detection/api-client";

const mocks = vi.hoisted(() => ({
  getBambooDashboard: vi.fn(),
  listBambooTasks: vi.fn(),
  getBambooRecord: vi.fn(),
  submitBambooStage: vi.fn(),
  getBambooOperations: vi.fn(),
}));

vi.mock("@form-detection/api-client", async (importOriginal) => ({
  ...await importOriginal<typeof import("@form-detection/api-client")>(),
  mobileApiClient: mocks,
}));
vi.mock("../device", () => ({ createMobileClientId: () => "stage-sort-key", getMobileDeviceId: () => "device-1" }));

import { MobileBambooProcessPage } from "../MobileBambooProcessPage";
import { MobileSessionProvider } from "../session/MobileSessionProvider";

const session = {
  employee_name: "王分选",
  employee_code: "E-SORT",
  team_name: "一厂生产组",
  position: "分选工",
  roles: ["WORKER"],
  allowed_form_types: [],
  allowed_processes: ["BAMBOO_PROCESS"],
  factory_id: "FACTORY-A",
  factory_name: "竹丝一厂",
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
  base_info: { cage_no: "3-018", length: "2.3", grade: "A", bundle_count: 16 },
  current_stage: "SORT",
  status: "ACTIVE",
  revision: 1,
  created_by: "E-SORT",
  created_at: "2026-07-22T02:30:00Z",
  updated_at: "2026-07-22T02:30:00Z",
  submissions: [],
};

const jointRecord: BambooRecord = {
  ...sortingRecord,
  record_id: "JOINT-18",
  display_no: "JG-20260722-018",
  source_type: "SORTING_RECORD",
  source_ref: sortingRecord.display_no,
  form_type: "DIPPING_DRYING",
  source_record_id: sortingRecord.record_id,
  source_snapshot: { record_id: sortingRecord.record_id, display_no: sortingRecord.display_no, revision: 1, base_info: sortingRecord.base_info, source_status: "CURRENT" },
  current_stage: "DIPPING",
};

const sessionClient = {
  getSession: vi.fn().mockResolvedValue(session),
  login: vi.fn(),
  logout: vi.fn(),
} as unknown as MobileApiClient;

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <MobileSessionProvider client={sessionClient}>
        <Routes>
          <Route path="mobile/record/bamboo-process" element={<MobileBambooProcessPage />} />
          <Route path="mobile/record/bamboo-process/:recordId" element={<MobileBambooProcessPage />} />
        </Routes>
      </MobileSessionProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionClient.getSession = vi.fn().mockResolvedValue(session);
  mocks.getBambooDashboard.mockResolvedValue({ available: 2, waiting: 0, completed: 0 });
  mocks.listBambooTasks.mockResolvedValue({ bucket: "available", tasks: [sortingRecord, jointRecord] });
  mocks.getBambooRecord.mockResolvedValue(sortingRecord);
  mocks.submitBambooStage.mockResolvedValue({ ...sortingRecord, current_stage: "SUPERVISOR", revision: 2 });
  mocks.getBambooOperations.mockResolvedValue({ payroll_facts: [], inspections: [], corrections: [] });
});

afterEach(cleanup);

describe("bamboo mobile workflow", () => {
  it("renders independent sorting and joint fixtures in the work list", async () => {
    renderRoute("/mobile/record/bamboo-process");
    expect(await screen.findByText(sortingRecord.display_no)).toBeTruthy();
    expect(screen.getByText(jointRecord.display_no)).toBeTruthy();
    expect(mocks.listBambooTasks).toHaveBeenCalledWith("available");
  });

  it("submits SORTING moisture only to the SORT stage", async () => {
    const user = userEvent.setup();
    renderRoute("/mobile/record/bamboo-process/SORT-18");

    expect(await screen.findByRole("heading", { name: "分选表详情" })).toBeTruthy();
    expect(screen.getAllByLabelText(/含水率检测点/)).toHaveLength(8);
    await user.type(screen.getByLabelText("含水率检测点 1"), "12");
    await user.type(screen.getByLabelText("含水率检测点 2"), "14");
    await user.click(screen.getByRole("button", { name: "核对并提交分选记录" }));
    expect(screen.getByRole("heading", { name: "签字前核对" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "确认提交" }));

    await waitFor(() => expect(mocks.submitBambooStage).toHaveBeenCalledWith(
      "SORT-18",
      "SORT",
      { expected_revision: 1, device_id: "device-1", values: { moisture: [12, 14] } },
      "stage-sort-key",
    ));
  });

  it("shows V3 dipping fields only on the joint DIPPING stage", async () => {
    mocks.getBambooRecord.mockResolvedValue(jointRecord);
    sessionClient.getSession = vi.fn().mockResolvedValue({ ...session, employee_name: "李浸胶", bamboo_role: "DIPPING_OPERATOR", position: "浸胶工" });
    renderRoute("/mobile/record/bamboo-process/JOINT-18");

    expect(await screen.findByRole("heading", { name: "浸胶+干燥联合表详情" })).toBeTruthy();
    expect(screen.getByText("胶前重")).toBeTruthy();
    expect(screen.getByText("胶后重")).toBeTruthy();
    expect(screen.getByText("上胶量")).toBeTruthy();
    expect(screen.getByText("胶液批次")).toBeTruthy();
    expect(screen.queryByText("干燥架号")).toBeNull();
    expect(screen.queryByRole("button", { name: "核对并提交分选记录" })).toBeNull();
  });
});
