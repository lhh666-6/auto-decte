export type BambooDraftScope = {
  employeeCode: string;
  factoryId: string;
  deviceId: string;
  recordId: string;
  stage: string;
};

const PREFIX = "bamboo-v3-draft";

export function bambooDraftKey(scope: BambooDraftScope): string {
  return [PREFIX, scope.employeeCode, scope.factoryId, scope.deviceId, scope.recordId, scope.stage]
    .map((part) => encodeURIComponent(part))
    .join(":");
}

export function readBambooDraft<T>(scope: BambooDraftScope): T | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(bambooDraftKey(scope));
    return raw ? JSON.parse(raw) as T : null;
  } catch {
    return null;
  }
}

export function writeBambooDraft<T>(scope: BambooDraftScope, value: T): boolean {
  if (typeof localStorage === "undefined") return false;
  try {
    localStorage.setItem(bambooDraftKey(scope), JSON.stringify(value));
    window.dispatchEvent(new Event("bamboo-drafts-changed"));
    return true;
  } catch {
    return false;
  }
}

export function clearBambooDraft(scope: BambooDraftScope): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.removeItem(bambooDraftKey(scope));
    window.dispatchEvent(new Event("bamboo-drafts-changed"));
  } catch {
    // The server submission remains authoritative when browser cleanup fails.
  }
}

export function countBambooDrafts(employeeCode: string, factoryId: string, deviceId: string): number {
  if (typeof localStorage === "undefined") return 0;
  const prefix = [PREFIX, employeeCode, factoryId, deviceId].map((part) => encodeURIComponent(part)).join(":");
  try {
    return Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index))
      .filter((key) => key?.startsWith(`${prefix}:`)).length;
  } catch {
    return 0;
  }
}
