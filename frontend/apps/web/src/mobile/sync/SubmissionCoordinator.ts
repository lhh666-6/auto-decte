/**
 * Submission coordinator — write-through IndexedDB → API.
 *
 * 1. Save draft to IndexedDB
 * 2. Enqueue in outbox
 * 3. Try network submission
 * 4. On success: remove from outbox
 * 5. On failure: exponential backoff retry
 *
 * Serial per-owner to avoid ordering-dependent resource conflicts.
 */

import { mobileFetch } from "../auth";
import { enqueue, listPending, markFailed, markSubmitting, remove } from "../storage/outbox";

export interface SubmissionPayload {
  form_type: string;
  definition_version_id: string;
  mode: string;
  subject_employee_code: string;
  device_id: string;
  values: Record<string, unknown>;
}

let _syncing = false;

export async function submitWithOutbox(
  payload: SubmissionPayload,
  idempotencyKey: string,
): Promise<{ submission_id: string; idempotent: boolean }> {
  // 1. Enqueue
  await enqueue({
    outboxId: idempotencyKey,
    operation: "CREATE_ELECTRONIC_FORM",
    idempotencyKey,
    payload,
  });

  // 2. Try immediately
  return flushOutbox();
}

async function flushOutbox(): Promise<{ submission_id: string; idempotent: boolean }> {
  if (_syncing) {
    // Serialise — avoid concurrent submissions for the same owner
    await new Promise((r) => setTimeout(r, 100));
    return flushOutbox();
  }
  _syncing = true;
  try {
    const pending = await listPending();
    let lastResult: { submission_id: string; idempotent: boolean } | null = null;

    for (const entry of pending) {
      await markSubmitting(entry.outboxId);
      try {
        const res = await mobileFetch("/api/v1/mobile/submissions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": entry.idempotencyKey,
          },
          body: JSON.stringify(entry.payload),
        });
        if (res.ok) {
          const data = (await res.json()) as { submission_id: string; idempotent: boolean };
          await remove(entry.outboxId);
          lastResult = data;
        } else {
          const body = await res.json().catch(() => ({}));
          const err = (body as { detail?: string }).detail ?? res.statusText;
          if (res.status === 409) {
            // Business conflict — do not retry
            await remove(entry.outboxId);
          } else if (res.status >= 500) {
            await markFailed(entry.outboxId, err);
          } else {
            await markFailed(entry.outboxId, err);
          }
        }
      } catch (err) {
        await markFailed(
          entry.outboxId,
          err instanceof Error ? err.message : "网络错误",
        );
      }
    }
    if (!lastResult) throw new Error("同步失败，请检查网络后重试");
    return lastResult;
  } finally {
    _syncing = false;
  }
}

/** Called when the browser comes back online. */
export function onOnline(callback: () => void): () => void {
  const handler = () => callback();
  window.addEventListener("online", handler);
  return () => window.removeEventListener("online", handler);
}
