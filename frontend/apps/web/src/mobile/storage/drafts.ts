/**
 * IndexedDB draft persistence — offline-first form drafts.
 *
 * Keys are scoped to owner + device so public-device IndexedDB data
 * doesn't leak between workers.
 */

import { getDB } from "./db";

export interface LocalDraft {
  localDraftId: string;
  owner: string;
  deviceId: string;
  formType: string;
  definitionVersionId: string;
  values: Record<string, unknown>;
  updatedAt: string;
}

function draftKey(owner: string, deviceId: string, localDraftId: string): string {
  return `${owner}:${deviceId}:${localDraftId}`;
}

export async function saveDraft(draft: LocalDraft): Promise<void> {
  const db = await getDB();
  draft.updatedAt = new Date().toISOString();
  await db.put("drafts", { ...draft, localDraftId: draftKey(draft.owner, draft.deviceId, draft.localDraftId) });
}

export async function listDrafts(
  owner: string,
  deviceId: string,
): Promise<LocalDraft[]> {
  const db = await getDB();
  const all = await db.getAll("drafts");
  const prefix = `${owner}:${deviceId}:`;
  return all
    .filter((d) => d.localDraftId.startsWith(prefix))
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function deleteDraft(localDraftId: string): Promise<void> {
  const db = await getDB();
  await db.delete("drafts", localDraftId);
}

export async function deleteAllDrafts(owner: string, deviceId: string): Promise<void> {
  const drafts = await listDrafts(owner, deviceId);
  const db = await getDB();
  const tx = db.transaction("drafts", "readwrite");
  for (const d of drafts) {
    tx.store.delete(d.localDraftId);
  }
  await tx.done;
}
