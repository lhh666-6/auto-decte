const DEVICE_ID_KEY = "mobile_device_id";

export function createMobileClientId(prefix = "mobile"): string {
  const randomUuid = globalThis.crypto?.randomUUID?.();
  if (randomUuid) return randomUuid;
  const randomPart = Math.random().toString(36).slice(2, 12);
  return `${prefix}-${Date.now().toString(36)}-${randomPart}`;
}

export function getMobileDeviceId(): string {
  const existing = localStorage.getItem(DEVICE_ID_KEY);
  if (existing) return existing;
  const created = createMobileClientId("device");
  localStorage.setItem(DEVICE_ID_KEY, created);
  return created;
}
