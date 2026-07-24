import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getAll: vi.fn(),
  get: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("./db", () => ({
  getDB: vi.fn().mockResolvedValue({
    getAll: mocks.getAll,
    get: mocks.get,
    put: mocks.put,
    delete: mocks.delete,
  }),
}));

import { countAll, countPending, listAll, listPending } from "./outbox";
import type { OutboxEntry } from "./outbox";

function makeEntry(overrides: Partial<OutboxEntry> = {}): OutboxEntry {
  return {
    outboxId: `entry-${Math.random().toString(36).slice(2, 8)}`,
    owner: "EMP-A",
    operation: "CREATE_ELECTRONIC_FORM",
    idempotencyKey: `key-${Math.random().toString(36).slice(2, 8)}`,
    payload: {},
    attemptCount: 0,
    nextRetryAt: new Date(0).toISOString(),
    lastError: null,
    lastErrorCode: null,
    lastRequestId: null,
    status: "PENDING",
    createdAt: new Date().toISOString(),
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ── TEST 1: listPending is owner-scoped ──
describe("listPending owner isolation", () => {
  it("returns only entries matching the requested owner", async () => {
    const a1 = makeEntry({ outboxId: "A1", owner: "EMP-A" });
    const a2 = makeEntry({ outboxId: "A2", owner: "EMP-A" });
    const b1 = makeEntry({ outboxId: "B1", owner: "EMP-B" });

    mocks.getAll.mockResolvedValue([a1, a2, b1]);

    const resultA = await listPending("EMP-A");
    const resultB = await listPending("EMP-B");

    expect(resultA).toHaveLength(2);
    expect(resultA.map((e) => e.outboxId).sort()).toEqual(["A1", "A2"]);
    expect(resultB).toHaveLength(1);
    expect(resultB[0].outboxId).toBe("B1");
  });

  it("does not return entries from other owners (no cross-contamination)", async () => {
    mocks.getAll.mockResolvedValue([makeEntry({ outboxId: "B1", owner: "EMP-B" })]);

    const result = await listPending("EMP-A");

    expect(result).toHaveLength(0);
  });
});

// ── TEST 2: listAll is owner-scoped ──
describe("listAll owner isolation", () => {
  it("returns only the requested owner when owner is provided", async () => {
    mocks.getAll.mockResolvedValue([
      makeEntry({ outboxId: "A1", owner: "EMP-A", status: "PENDING" }),
      makeEntry({ outboxId: "A2", owner: "EMP-A", status: "FAILED_FINAL" }),
      makeEntry({ outboxId: "B1", owner: "EMP-B", status: "PENDING" }),
    ]);

    const result = await listAll("EMP-A");

    expect(result).toHaveLength(2);
    expect(result.every((e) => e.owner === "EMP-A")).toBe(true);
  });

  it("returns all entries when no owner is provided (backward compatibility)", async () => {
    mocks.getAll.mockResolvedValue([
      makeEntry({ outboxId: "A1", owner: "EMP-A" }),
      makeEntry({ outboxId: "B1", owner: "EMP-B" }),
    ]);

    const result = await listAll();

    expect(result).toHaveLength(2);
  });
});

// ── TEST 3: counts are owner-scoped ──
describe("owner-scoped counts", () => {
  it("countAll only counts entries for the specified owner", async () => {
    mocks.getAll.mockResolvedValue([
      makeEntry({ owner: "EMP-A" }),
      makeEntry({ owner: "EMP-A" }),
      makeEntry({ owner: "EMP-B" }),
      makeEntry({ owner: "EMP-B" }),
      makeEntry({ owner: "EMP-B" }),
    ]);

    expect(await countAll("EMP-A")).toBe(2);
    expect(await countAll("EMP-B")).toBe(3);
  });

  it("countPending only counts pending entries for the specified owner", async () => {
    mocks.getAll.mockResolvedValue([
      makeEntry({ outboxId: "A1", owner: "EMP-A", status: "PENDING" }),
      makeEntry({ outboxId: "A2", owner: "EMP-A", status: "FAILED_RETRYABLE" }),
      makeEntry({ outboxId: "A3", owner: "EMP-A", status: "FAILED_FINAL" }),
      makeEntry({ outboxId: "B1", owner: "EMP-B", status: "PENDING" }),
      makeEntry({ outboxId: "B2", owner: "EMP-B", status: "PENDING" }),
    ]);

    expect(await countPending("EMP-A")).toBe(2);
    expect(await countPending("EMP-B")).toBe(2);
  });
});

// ── TEST: logout count is owner-scoped ──
describe("logout pending count", () => {
  it("only shows the current user's pending count", async () => {
    mocks.getAll.mockResolvedValue([
      makeEntry({ owner: "EMP-A", status: "PENDING" }),
      makeEntry({ owner: "EMP-A", status: "PENDING" }),
      makeEntry({ owner: "EMP-B", status: "PENDING" }),
      makeEntry({ owner: "EMP-B", status: "PENDING" }),
      makeEntry({ owner: "EMP-B", status: "PENDING" }),
    ]);

    const countA = await countAll("EMP-A");
    const countB = await countAll("EMP-B");

    expect(countA).toBe(2);
    expect(countB).toBe(3);
  });
});
