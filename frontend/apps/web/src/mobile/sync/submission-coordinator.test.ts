import { beforeEach, describe, expect, it, vi } from "vitest";

import { MobileApiError } from "@form-detection/api-client";

const mocks = vi.hoisted(() => ({
  createSubmission: vi.fn(),
  enqueue: vi.fn(),
  listPending: vi.fn(),
  markFinal: vi.fn(),
  markRetryable: vi.fn(),
  markSubmitting: vi.fn(),
  remove: vi.fn(),
  resetPending: vi.fn(),
  deleteDraft: vi.fn(),
}));

vi.mock("@form-detection/api-client", async (importOriginal) => ({
  ...await importOriginal<typeof import("@form-detection/api-client")>(),
  mobileApiClient: { createSubmission: mocks.createSubmission },
}));

vi.mock("../storage/outbox", () => ({
  enqueue: mocks.enqueue,
  listPending: mocks.listPending,
  markFinal: mocks.markFinal,
  markRetryable: mocks.markRetryable,
  markSubmitting: mocks.markSubmitting,
  remove: mocks.remove,
  resetPending: mocks.resetPending,
}));

vi.mock("../storage/drafts", () => ({ deleteDraft: mocks.deleteDraft }));

import { flushPendingOutbox } from "./SubmissionCoordinator";

const payload = {
  form_type: "SELF_SHEET_PIECE",
  definition_version_id: "definition-1",
  mode: "SELF" as const,
  subject_employee_code: "E001",
  device_id: "device-1",
  values: { quantity: 3 },
};

const entry = {
  outboxId: "key-1",
  operation: "CREATE_ELECTRONIC_FORM",
  idempotencyKey: "key-1",
  payload,
  attemptCount: 0,
  nextRetryAt: "2026-07-21T00:00:00Z",
  lastError: null,
  lastErrorCode: null,
  lastRequestId: null,
  status: "PENDING" as const,
  createdAt: "2026-07-21T00:00:00Z",
  draftRef: { owner: "E001", deviceId: "device-1", localDraftId: "draft-1" },
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.listPending.mockResolvedValue([entry]);
});

describe("flushPendingOutbox", () => {
  it("shares one in-flight flush and reuses the stored idempotency key", async () => {
    let resolveReceipt!: (value: unknown) => void;
    mocks.createSubmission.mockImplementation(() => new Promise((resolve) => {
      resolveReceipt = resolve;
    }));

    const first = flushPendingOutbox();
    const second = flushPendingOutbox();
    await vi.waitFor(() => expect(mocks.createSubmission).toHaveBeenCalledTimes(1));
    resolveReceipt({ submission_id: "receipt-1", status: "NEEDS_REVIEW", submitted_at: "now", idempotent: false });

    await Promise.all([first, second]);
    expect(mocks.createSubmission).toHaveBeenCalledTimes(1);
    expect(mocks.createSubmission).toHaveBeenCalledWith(payload, "key-1");
  });

  it("deletes the outbox item and its source draft only after a receipt", async () => {
    mocks.createSubmission.mockResolvedValue({
      submission_id: "receipt-1",
      status: "NEEDS_REVIEW",
      submitted_at: "now",
      idempotent: false,
    });

    const result = await flushPendingOutbox();

    expect(result.succeeded).toBe(1);
    expect(mocks.remove).toHaveBeenCalledWith("key-1");
    expect(mocks.deleteDraft).toHaveBeenCalledWith("E001", "device-1", "draft-1");
  });

  it.each([403, 409, 422])("retains HTTP %s as a final failure", async (status) => {
    mocks.createSubmission.mockRejectedValue(new MobileApiError({
      title: "Rejected",
      status,
      code: status === 409 ? "IDEMPOTENCY_CONFLICT" : "SUBMISSION_REJECTED",
      detail: "提交内容不可接受",
      request_id: "request-1",
    }));

    const result = await flushPendingOutbox();

    expect(result.failedFinal).toBe(1);
    expect(mocks.markFinal).toHaveBeenCalledWith(
      "key-1",
      "提交内容不可接受",
      expect.objectContaining({ code: expect.any(String), requestId: "request-1" }),
    );
    expect(mocks.remove).not.toHaveBeenCalled();
  });

  it("pauses on 401 without consuming a retry attempt", async () => {
    mocks.createSubmission.mockRejectedValue(new MobileApiError({
      title: "Unauthorized",
      status: 401,
      code: "SESSION_EXPIRED",
      detail: "请重新登录",
      request_id: "request-2",
    }));

    const result = await flushPendingOutbox();

    expect(result.pausedForAuthentication).toBe(true);
    expect(mocks.resetPending).toHaveBeenCalledWith("key-1", "请重新登录", {
      code: "SESSION_EXPIRED",
      requestId: "request-2",
    });
    expect(mocks.markRetryable).not.toHaveBeenCalled();
  });

  it("retries network and server failures with backoff", async () => {
    mocks.createSubmission.mockRejectedValue(new TypeError("Failed to fetch"));

    const result = await flushPendingOutbox();

    expect(result.failedRetryable).toBe(1);
    expect(mocks.markRetryable).toHaveBeenCalledWith(
      "key-1",
      "网络连接失败，请稍后重试。",
      expect.objectContaining({ code: "NETWORK_ERROR" }),
    );
  });
});
