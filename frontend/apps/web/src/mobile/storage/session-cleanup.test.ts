import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  deleteAllDrafts: vi.fn(),
  clearSessionMetadata: vi.fn(),
  listAll: vi.fn(),
}));

vi.mock("./drafts", () => ({ deleteAllDrafts: mocks.deleteAllDrafts }));
vi.mock("./db", () => ({ clearSessionMetadata: mocks.clearSessionMetadata }));
vi.mock("./outbox", () => ({ listAll: mocks.listAll }));

import { cleanupSessionStorage, getPendingLogoutCount } from "./session-cleanup";

beforeEach(() => vi.clearAllMocks());

describe("shared-device session cleanup", () => {
  it("clears session metadata and current-owner drafts without deleting outbox", async () => {
    mocks.listAll.mockResolvedValue([{ outboxId: "keep-1" }]);

    expect(await getPendingLogoutCount()).toBe(1);
    await cleanupSessionStorage("E001", "device-1");

    expect(mocks.clearSessionMetadata).toHaveBeenCalledTimes(1);
    expect(mocks.deleteAllDrafts).toHaveBeenCalledWith("E001", "device-1");
    expect(mocks.listAll).toHaveBeenCalledTimes(1);
  });
});
