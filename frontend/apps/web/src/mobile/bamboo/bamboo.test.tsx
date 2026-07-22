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
  createBambooRecord: vi.fn(),
  submitBambooStage: vi.fn(),
}));

vi.mock("@form-detection/api-client", async (importOriginal) => ({
  ...await importOriginal<typeof import("@form-detection/api-client")>(),
  mobileApiClient: mocks,
}));

vi.mock("../device", () => ({ getMobileDeviceId: () => "device-1" }));

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

const sessionClient = {
  getSession: vi.fn().mockResolvedValue(session),
  login: vi.fn(),
  logout: vi.fn(),
} as unknown as MobileApiClient;

const record: BambooRecord = {
  record_id: "BR-18",
  display_no: "ZS-20260722-018",
  factory_id: "FACTORY-A",
  source_type: "MOBILE_CREATED",
  source_ref: "create-18",
  base_info: { cage_no: "3-018", length: "2.3", grade: "A", bundle_count: 16 },
  current_stage: "SORT",
  status: "ACTIVE",
  revision: 1,
  created_by: "E-SORT",
  created_at: "2026-07-22T02:30:00Z",
  updated_at: "2026-07-22T02:30:00Z",
  submissions: [],
};

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
  mocks.getBambooDashboard.mockResolvedValue({ available: 1, waiting: 0, completed: 0 });
  mocks.listBambooTasks.mockResolvedValue({ bucket: "available", tasks: [record] });
  mocks.getBambooRecord.mockResolvedValue(record);
  mocks.submitBambooStage.mockResolvedValue({
    ...record,
    current_stage: "DIPPING",
    revision: 2,
  });
});

afterEach(cleanup);

describe("bamboo mobile workflow", () => {
  it("shows only the records opened to the current role", async () => {
    renderRoute("/mobile/record/bamboo-process");

    expect(await screen.findByRole("heading", { name: "记录工作" })).toBeTruthy();
    expect(await screen.findByText("ZS-20260722-018")).toBeTruthy();
    expect(screen.queryByText("未开放记录")).toBeNull();
    expect(mocks.listBambooTasks).toHaveBeenCalledWith("available");
  });

  it("lets a sort operator adjust eight moisture points and confirm a signature", async () => {
    const user = userEvent.setup();
    renderRoute("/mobile/record/bamboo-process/BR-18");

    expect(await screen.findByRole("heading", { name: "竹丝工序记录" })).toBeTruthy();
    expect(screen.getAllByLabelText(/含水率检测点/)).toHaveLength(8);
    await user.click(screen.getByRole("button", { name: "增加检测点" }));
    expect(screen.getAllByLabelText(/含水率检测点/)).toHaveLength(9);
    await user.click(screen.getByRole("button", { name: "删除最后一个" }));
    expect(screen.getAllByLabelText(/含水率检测点/)).toHaveLength(8);

    await user.type(screen.getAllByLabelText(/含水率检测点/)[0]!, "12.5");
    await user.click(screen.getByRole("button", { name: "核对并签字" }));
    expect(screen.getByRole("heading", { name: "签字前核对" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "确认签字" }));

    await waitFor(() => expect(mocks.submitBambooStage).toHaveBeenCalledWith(
      "BR-18",
      "SORT",
      expect.objectContaining({ expected_revision: 1, device_id: "device-1" }),
      expect.any(String),
    ));
  });
});
