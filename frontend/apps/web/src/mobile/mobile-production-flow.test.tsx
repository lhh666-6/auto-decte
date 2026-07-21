// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import type { MobileApiClient } from "@form-detection/api-client";

const mocks = vi.hoisted(() => ({
  getAvailableForms: vi.fn(),
  getFormSchema: vi.fn(),
  getProductionContext: vi.fn(),
  getTeamMembers: vi.fn(),
  listDrafts: vi.fn(),
  listAll: vi.fn(),
  resetPending: vi.fn(),
  remove: vi.fn(),
  flushPendingOutbox: vi.fn(),
}));

vi.mock("@form-detection/api-client", async (importOriginal) => ({
  ...await importOriginal<typeof import("@form-detection/api-client")>(),
  mobileApiClient: {
    getAvailableForms: mocks.getAvailableForms,
    getFormSchema: mocks.getFormSchema,
    getProductionContext: mocks.getProductionContext,
    getTeamMembers: mocks.getTeamMembers,
  },
}));

vi.mock("./storage/drafts", () => ({ listDrafts: mocks.listDrafts }));
vi.mock("./storage/outbox", () => ({
  listAll: mocks.listAll,
  resetPending: mocks.resetPending,
  remove: mocks.remove,
}));
vi.mock("./sync/SubmissionCoordinator", () => ({
  flushPendingOutbox: mocks.flushPendingOutbox,
}));
vi.mock("./device", () => ({ getMobileDeviceId: () => "device-1" }));
vi.mock("./MobileFormEngine", () => ({
  MobileFormEngine: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

import { MobileDraftsPage } from "./MobileDraftsPage";
import { MobileOutboxPage } from "./MobileOutboxPage";
import { MobileTeamSheetPiecePage } from "./MobileTeamSheetPiecePage";
import { MobileSessionProvider } from "./session/MobileSessionProvider";

const session = {
  employee_name: "班组长",
  employee_code: "L001",
  team_name: "甲班",
  position: "班组长",
  roles: ["TEAM_LEADER"],
  allowed_form_types: ["TEAM_SHEET_PIECE_MEASUREMENT"],
  allowed_processes: [],
};

const sessionClient = {
  getSession: vi.fn().mockResolvedValue(session),
  login: vi.fn(),
  logout: vi.fn(),
} as unknown as MobileApiClient;

function renderPage(page: React.ReactNode) {
  render(
    <MemoryRouter>
      <MobileSessionProvider client={sessionClient}>{page}</MobileSessionProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionClient.getSession = vi.fn().mockResolvedValue(session);
});

afterEach(cleanup);

describe("mobile production flow", () => {
  it("loads owner-scoped drafts from IndexedDB without an HTTP request", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    mocks.listDrafts.mockResolvedValue([{
      storageKey: "L001:device-1:draft-1",
      localDraftId: "draft-1",
      owner: "L001",
      deviceId: "device-1",
      formType: "SHEET_PIECE_MEASUREMENT",
      definitionVersionId: "definition-1",
      values: {},
      updatedAt: "2026-07-21T00:00:00Z",
    }]);

    renderPage(<MobileDraftsPage />);

    expect(await screen.findByText("配片工作记录")).toBeTruthy();
    expect(mocks.listDrafts).toHaveBeenCalledWith("L001", "device-1");
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("keeps final outbox failures visible with a reason and retry action", async () => {
    mocks.listAll.mockResolvedValue([{
      outboxId: "key-1",
      operation: "CREATE_ELECTRONIC_FORM",
      idempotencyKey: "key-1",
      payload: { form_type: "SHEET_PIECE_MEASUREMENT" },
      attemptCount: 1,
      nextRetryAt: "2026-07-21T00:00:00Z",
      lastError: "字段不符合定义",
      lastErrorCode: "SUBMISSION_FIELDS_INVALID",
      lastRequestId: "request-1",
      status: "FAILED_FINAL",
      createdAt: "2026-07-21T00:00:00Z",
    }]);
    mocks.flushPendingOutbox.mockResolvedValue({ succeeded: 0 });

    renderPage(<MobileOutboxPage />);

    expect(await screen.findByText("字段不符合定义")).toBeTruthy();
    expect(screen.getByText("请求编号：request-1")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(mocks.resetPending).toHaveBeenCalledWith("key-1"));
  });

  it("loads selectable team members from the server instead of component constants", async () => {
    mocks.getFormSchema.mockResolvedValue({
      form_type: "TEAM_SHEET_PIECE_MEASUREMENT",
      title: "班组配片记录",
      modes: ["TEAM_LEADER_BATCH"],
      definition_version_id: "definition-1",
      version: "1",
      fields: [],
    });
    mocks.getProductionContext.mockResolvedValue({
      context_id: "context-1",
      team_id: "team-1",
      date: "2026-07-21",
      shift: "白班",
      work_orders: [],
      products: [],
      specs: [],
      pieces_per_block: null,
    });
    mocks.getTeamMembers.mockResolvedValue({
      members: [{ employee_code: "E009", employee_name: "王五" }],
    });

    renderPage(<MobileTeamSheetPiecePage />);

    expect(await screen.findByRole("option", { name: "王五 (E009)" })).toBeTruthy();
    expect(screen.queryByText(/张三/)).toBeNull();
    expect(mocks.getTeamMembers).toHaveBeenCalledTimes(1);
  });
});
