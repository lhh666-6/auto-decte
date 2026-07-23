import { useEffect } from "react";

import { mobileApiClient } from "@form-detection/api-client";

import {
  BAMBOO_NOTIFICATION_PREFERENCE_CHANGED,
  deliverUnreadBambooNotifications,
  getBambooNotificationPreference,
} from "./system-notifications";

const POLL_INTERVAL_MS = 30_000;

export function useBambooSystemNotifications(employeeCode: string | undefined, active: boolean): void {
  useEffect(() => {
    if (!employeeCode || !active) return undefined;
    let polling = false;
    let stopped = false;
    const poll = async () => {
      if (polling || stopped || getBambooNotificationPreference(employeeCode) !== "enabled") return;
      polling = true;
      try {
        const response = await mobileApiClient.listBambooNotifications();
        if (!stopped) await deliverUnreadBambooNotifications(employeeCode, response.items);
      } catch {
        // Durable messages remain in the message center; popup delivery is best-effort only.
      } finally {
        polling = false;
      }
    };
    const onVisible = () => { if (document.visibilityState === "visible") void poll(); };
    const onPreferenceChanged = () => { void poll(); };
    const timer = window.setInterval(() => { void poll(); }, POLL_INTERVAL_MS);
    window.addEventListener("focus", onPreferenceChanged);
    window.addEventListener(BAMBOO_NOTIFICATION_PREFERENCE_CHANGED, onPreferenceChanged);
    document.addEventListener("visibilitychange", onVisible);
    void poll();
    return () => {
      stopped = true;
      window.clearInterval(timer);
      window.removeEventListener("focus", onPreferenceChanged);
      window.removeEventListener(BAMBOO_NOTIFICATION_PREFERENCE_CHANGED, onPreferenceChanged);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [active, employeeCode]);
}
