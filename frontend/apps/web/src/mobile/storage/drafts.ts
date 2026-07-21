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

export interface StoredDraft extends LocalDraft {
  storageKey: string;
}

function draftKey(owner: string, deviceId: string, localDraftId: string): string {
  return `${owner}:${deviceId}:${localDraftId}`;
}

export async function saveDraft(draft: LocalDraft): Promise<StoredDraft> {
  const db = await getDB();
  const stored = {
    ...draft,
    storageKey: draftKey(draft.owner, draft.deviceId, draft.localDraftId),
    updatedAt: new Date().toISOString(),
  };
  await db.put("drafts", stored);
  return stored;
}

export async function listDrafts(
  owner: string,
  deviceId: string,
): Promise<StoredDraft[]> {
  const db = await getDB();
  const all = await db.getAll("drafts");
  return all
    .filter((d) => d.owner === owner && d.deviceId === deviceId)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function deleteDraft(
  owner: string,
  deviceId: string,
  localDraftId: string,
): Promise<void> {
  const db = await getDB();
  await db.delete("drafts", draftKey(owner, deviceId, localDraftId));
}

export async function deleteAllDrafts(owner: string, deviceId: string): Promise<void> {
  const drafts = await listDrafts(owner, deviceId);
  const db = await getDB();
  const tx = db.transaction("drafts", "readwrite");
  for (const d of drafts) {
    tx.store.delete(d.storageKey);
  }
  await tx.done;
}
