/**
 * IndexedDB outbox — offline submission queue.
 *
 * Every submission writes here FIRST, then tries the network.
 * On receipt success the entry is deleted. On failure it stays
 * for retry with exponential backoff.
 */

import { getDB } from "./db";

export interface OutboxEntry {
  outboxId: string;
  operation: string;
  idempotencyKey: string;
  payload: Record<string, unknown>;
  attemptCount: number;
  nextRetryAt: string;
  lastError: string | null;
  status: "PENDING" | "SUBMITTING" | "FAILED_RETRYABLE" | "FAILED_FINAL";
  createdAt: string;
}

export async function enqueue(entry: Omit<OutboxEntry, "attemptCount" | "nextRetryAt" | "lastError" | "status" | "createdAt">): Promise<void> {
  const db = await getDB();
  const now = new Date().toISOString();
  await db.put("outbox", {
    ...entry,
    attemptCount: 0,
    nextRetryAt: now,
    lastError: null,
    status: "PENDING",
    createdAt: now,
  });
}

export async function markSubmitting(outboxId: string): Promise<void> {
  const db = await getDB();
  const entry = await db.get("outbox", outboxId);
  if (!entry) return;
  entry.status = "SUBMITTING";
  await db.put("outbox", entry);
}

export async function markFailed(outboxId: string, error: string): Promise<void> {
  const db = await getDB();
  const entry = await db.get("outbox", outboxId);
  if (!entry) return;
  entry.attemptCount += 1;
  entry.lastError = error;

  // Exponential backoff: 5s, 30s, 2min, 10min, 30min
  const delays = [5_000, 30_000, 120_000, 600_000, 1_800_000];
  const delay = delays[Math.min(entry.attemptCount - 1, delays.length - 1)];
  entry.nextRetryAt = new Date(Date.now() + delay).toISOString();

  entry.status = entry.attemptCount >= 8 ? "FAILED_FINAL" : "FAILED_RETRYABLE";
  await db.put("outbox", entry);
}

export async function remove(outboxId: string): Promise<void> {
  const db = await getDB();
  await db.delete("outbox", outboxId);
}

export async function listPending(): Promise<OutboxEntry[]> {
  const db = await getDB();
  const all = await db.getAll("outbox");
  const now = Date.now();
  return all.filter(
    (e) =>
      (e.status === "PENDING" || e.status === "FAILED_RETRYABLE") &&
      new Date(e.nextRetryAt).getTime() <= now,
  );
}

export async function listAll(): Promise<OutboxEntry[]> {
  const db = await getDB();
  return db.getAll("outbox");
}

export async function countPending(): Promise<number> {
  const pending = await listPending();
  return pending.length;
}
