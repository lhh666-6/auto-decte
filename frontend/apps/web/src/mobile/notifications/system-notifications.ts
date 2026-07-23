import type { BambooNotification } from "@form-detection/api-client";

export type BambooNotificationPreference = "disabled" | "enabled" | "denied" | "unsupported";
export type BambooNotificationPresenter = (message: BambooNotification) => Promise<boolean>;

const preferenceKey = (employeeCode: string) => `bamboo-system-notifications:${employeeCode}`;
const deliveredKey = (employeeCode: string) => `bamboo-system-notification-delivered:${employeeCode}`;
export const BAMBOO_NOTIFICATION_PREFERENCE_CHANGED = "bamboo-notification-preference-changed";

function notificationApi(): typeof Notification | null {
  return typeof window !== "undefined" && "Notification" in window ? window.Notification : null;
}

export function getBambooNotificationPreference(employeeCode: string): BambooNotificationPreference {
  const api = notificationApi();
  if (!api) return "unsupported";
  if (api.permission === "denied") return "denied";
  return localStorage.getItem(preferenceKey(employeeCode)) === "enabled" && api.permission === "granted"
    ? "enabled"
    : "disabled";
}

export async function requestBambooNotificationPermission(employeeCode: string): Promise<BambooNotificationPreference> {
  const api = notificationApi();
  if (!api) return "unsupported";
  const permission = api.permission === "default" ? await api.requestPermission() : api.permission;
  if (permission === "granted") {
    localStorage.setItem(preferenceKey(employeeCode), "enabled");
    window.dispatchEvent(new Event(BAMBOO_NOTIFICATION_PREFERENCE_CHANGED));
    return "enabled";
  }
  localStorage.removeItem(preferenceKey(employeeCode));
  window.dispatchEvent(new Event(BAMBOO_NOTIFICATION_PREFERENCE_CHANGED));
  return permission === "denied" ? "denied" : "disabled";
}

export async function showBambooSystemNotification(message: BambooNotification): Promise<boolean> {
  const api = notificationApi();
  if (!api || api.permission !== "granted") return false;
  const options: NotificationOptions = {
    body: message.body,
    icon: "/icons/icon-192x192.png",
    tag: `bamboo-${message.notification_id}`,
    data: { notificationId: message.notification_id },
  };
  try {
    const registration = "serviceWorker" in navigator
      ? await navigator.serviceWorker.getRegistration()
      : undefined;
    if (registration) await registration.showNotification(message.title, options);
    else new api(message.title, options);
    return true;
  } catch {
    return false;
  }
}

export async function deliverUnreadBambooNotifications(
  employeeCode: string,
  messages: BambooNotification[],
  show: BambooNotificationPresenter = showBambooSystemNotification,
): Promise<number> {
  if (localStorage.getItem(preferenceKey(employeeCode)) !== "enabled") return 0;
  const delivered = new Set<string>(JSON.parse(localStorage.getItem(deliveredKey(employeeCode)) ?? "[]") as string[]);
  const pending = messages.filter((item) => item.read_at === null && !delivered.has(item.notification_id)).slice(0, 3);
  let count = 0;
  for (const message of pending) {
    if (await show(message)) {
      delivered.add(message.notification_id);
      count += 1;
    }
  }
  if (count > 0) {
    localStorage.setItem(deliveredKey(employeeCode), JSON.stringify(Array.from(delivered).slice(-200)));
  }
  return count;
}
