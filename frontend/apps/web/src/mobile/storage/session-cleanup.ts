import { deleteAllDrafts } from "./drafts";
import { clearSessionMetadata } from "./db";
import { listAll } from "./outbox";

export async function getPendingLogoutCount(): Promise<number> {
  return (await listAll()).length;
}

export async function cleanupSessionStorage(owner: string, deviceId: string): Promise<void> {
  await clearSessionMetadata();
  await deleteAllDrafts(owner, deviceId);
}
