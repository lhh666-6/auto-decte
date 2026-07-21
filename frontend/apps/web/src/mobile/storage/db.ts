/**
 * IndexedDB schema for industrial-form-pwa.
 *
 * Per Task 6 of the PWA plan:
 * - drafts: owner + device + local_draft_id scoped
 * - outbox: operation, payload, idempotency key, attempt count, next retry
 * - reference_snapshots: cached form definitions with server version/etag
 * - session_metadata: non-sensitive display info only (no cookies or PINs)
 */

import { openDB, type DBSchema, type IDBPDatabase } from "idb";

export interface IndustrialFormPWASchema extends DBSchema {
  drafts: {
    key: string; // "owner:device:local_draft_id"
    value: {
      storageKey: string;
      localDraftId: string;
      owner: string;
      deviceId: string;
      formType: string;
      definitionVersionId: string;
      values: Record<string, unknown>;
      updatedAt: string;
    };
  };
  outbox: {
    key: string; // uuid
    value: {
      outboxId: string;
      operation: string;
      idempotencyKey: string;
      payload: Record<string, unknown>;
      attemptCount: number;
      nextRetryAt: string;
      lastError: string | null;
      lastErrorCode: string | null;
      lastRequestId: string | null;
      status: "PENDING" | "SUBMITTING" | "FAILED_RETRYABLE" | "FAILED_FINAL";
      createdAt: string;
      draftRef?: { owner: string; deviceId: string; localDraftId: string };
    };
    indexes: { "by-status": string };
  };
  referenceSnapshots: {
    key: string; // "definition:{formType}"
    value: {
      cacheKey: string;
      data: unknown;
      serverVersion: string;
      cachedAt: string;
    };
  };
  sessionMetadata: {
    key: string;
    value: {
      employeeName: string;
      employeeCode: string;
      teamName: string;
      position: string;
      roles: string[];
      updatedAt: string;
    };
  };
}

let _dbPromise: Promise<IDBPDatabase<IndustrialFormPWASchema>> | null = null;

export function getDB(): Promise<IDBPDatabase<IndustrialFormPWASchema>> {
  if (!_dbPromise) {
    _dbPromise = openDB<IndustrialFormPWASchema>("industrial-form-pwa", 2, {
      upgrade(db, oldVersion) {
        if (oldVersion < 2 && db.objectStoreNames.contains("drafts")) {
          db.deleteObjectStore("drafts");
        }
        if (!db.objectStoreNames.contains("drafts")) {
          db.createObjectStore("drafts", { keyPath: "storageKey" });
        }
        const outbox = db.objectStoreNames.contains("outbox")
          ? null
          : db.createObjectStore("outbox", { keyPath: "outboxId" });
        if (outbox && !outbox.indexNames.contains("by-status")) {
          outbox.createIndex("by-status", "status");
        }
        if (!db.objectStoreNames.contains("referenceSnapshots")) {
          db.createObjectStore("referenceSnapshots", { keyPath: "cacheKey" });
        }
        if (!db.objectStoreNames.contains("sessionMetadata")) {
          db.createObjectStore("sessionMetadata");
        }
      },
    });
  }
  return _dbPromise;
}

/** Close the DB connection (e.g., on logout). */
export function closeDB(): void {
  if (_dbPromise) {
    void _dbPromise.then(
      (db) => db.close(),
      (error: unknown) => console.warn("[PWA] failed to close IndexedDB", error),
    );
    _dbPromise = null;
  }
}

export async function clearSessionMetadata(): Promise<void> {
  const db = await getDB();
  await db.clear("sessionMetadata");
}
