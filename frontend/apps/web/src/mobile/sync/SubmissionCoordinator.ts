import {
  MobileApiError,
  mobileApiClient,
  type MobileSubmissionInput,
  type MobileSubmissionReceipt,
} from "@form-detection/api-client";
import { deleteDraft } from "../storage/drafts";
import {
  enqueue,
  listPending,
  markFinal,
  markRetryable,
  markSubmitting,
  remove,
  resetPending,
} from "../storage/outbox";

export type SubmissionPayload = MobileSubmissionInput;

export interface DraftReference {
  owner: string;
  deviceId: string;
  localDraftId: string;
}

export interface FlushResult {
  succeeded: number;
  failedRetryable: number;
  failedFinal: number;
  pausedForAuthentication: boolean;
  receipts: MobileSubmissionReceipt[];
}

let activeFlush: Promise<FlushResult> | null = null;
let syncPaused = false;

export async function submitWithOutbox(
  payload: SubmissionPayload,
  idempotencyKey: string,
  draftRef?: DraftReference,
): Promise<MobileSubmissionReceipt | null> {
  await enqueue({
    outboxId: idempotencyKey,
    operation: "CREATE_ELECTRONIC_FORM",
    idempotencyKey,
    owner: draftRef?.owner ?? "",
    payload: payload as unknown as Record<string, unknown>,
    draftRef,
  });
  const result = await flushPendingOutbox();
  return result.receipts.at(-1) ?? null;
}

export function flushPendingOutbox(): Promise<FlushResult> {
  if (syncPaused) {
    return Promise.resolve({
      succeeded: 0,
      failedRetryable: 0,
      failedFinal: 0,
      pausedForAuthentication: true,
      receipts: [],
    });
  }
  if (activeFlush) return activeFlush;
  const pending = runFlush();
  activeFlush = pending;
  const clear = () => {
    if (activeFlush === pending) activeFlush = null;
  };
  void pending.then(clear, clear);
  return pending;
}

export async function pauseOutboxSync(): Promise<void> {
  syncPaused = true;
  if (activeFlush) await activeFlush;
}

export function resumeOutboxSync(): void {
  syncPaused = false;
}

async function runFlush(): Promise<FlushResult> {
  const result: FlushResult = {
    succeeded: 0,
    failedRetryable: 0,
    failedFinal: 0,
    pausedForAuthentication: false,
    receipts: [],
  };
  const pending = await listPending();
  for (const entry of pending) {
    await markSubmitting(entry.outboxId);
    try {
      const receipt = await mobileApiClient.createSubmission(
        entry.payload as unknown as MobileSubmissionInput,
        entry.idempotencyKey,
      );
      await remove(entry.outboxId);
      if (entry.draftRef) {
        await deleteDraft(
          entry.draftRef.owner,
          entry.draftRef.deviceId,
          entry.draftRef.localDraftId,
        );
      }
      result.succeeded += 1;
      result.receipts.push(receipt);
    } catch (cause) {
      if (cause instanceof MobileApiError) {
        const meta = { code: cause.code, requestId: cause.problem.request_id };
        if (cause.status === 401) {
          await resetPending(entry.outboxId, cause.problem.detail, meta);
          result.pausedForAuthentication = true;
          break;
        }
        if ([403, 409, 422].includes(cause.status) || cause.status < 500) {
          await markFinal(entry.outboxId, cause.problem.detail, meta);
          result.failedFinal += 1;
          continue;
        }
        await markRetryable(entry.outboxId, cause.problem.detail, meta);
        result.failedRetryable += 1;
        continue;
      }
      await markRetryable(entry.outboxId, "网络连接失败，请稍后重试。", {
        code: "NETWORK_ERROR",
      });
      result.failedRetryable += 1;
    }
  }
  return result;
}

export function installOnlineFlush(): () => void {
  const handler = () => { void flushPendingOutbox(); };
  window.addEventListener("online", handler);
  return () => window.removeEventListener("online", handler);
}
