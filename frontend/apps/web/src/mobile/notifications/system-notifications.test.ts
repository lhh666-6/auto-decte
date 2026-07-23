// @vitest-environment jsdom

import { beforeEach, expect, it, vi } from "vitest";

import type { BambooNotification } from "@form-detection/api-client";

import {
  deliverUnreadBambooNotifications,
  getBambooNotificationPreference,
  requestBambooNotificationPermission,
} from "./system-notifications";

const message: BambooNotification = {
  notification_id: "NOTICE-1",
  category: "PERSONNEL_TRANSFER_COMPLETED",
  title: "岗位调动已完成",
  body: "您已调动到目标工厂",
  link: null,
  payload: {},
  created_at: "2026-07-23T03:00:00Z",
  read_at: null,
};

beforeEach(() => localStorage.clear());

it("requests permission only through the explicit enable operation", async () => {
  let permission: NotificationPermission = "default";
  const requestPermission = vi.fn().mockImplementation(async () => {
    permission = "granted";
    return permission;
  });
  Object.defineProperty(window, "Notification", {
    configurable: true,
    value: { get permission() { return permission; }, requestPermission },
  });

  expect(getBambooNotificationPreference("ZS001")).toBe("disabled");
  expect(requestPermission).not.toHaveBeenCalled();
  expect(await requestBambooNotificationPermission("ZS001")).toBe("enabled");
  expect(requestPermission).toHaveBeenCalledTimes(1);
  expect(getBambooNotificationPreference("ZS001")).toBe("enabled");
});

it("keeps denied notification permission disabled", async () => {
  Object.defineProperty(window, "Notification", {
    configurable: true,
    value: { permission: "denied", requestPermission: vi.fn() },
  });

  expect(await requestBambooNotificationPermission("ZS001")).toBe("denied");
  expect(getBambooNotificationPreference("ZS001")).toBe("denied");
});

it("shows each unread durable message only once without marking it read", async () => {
  localStorage.setItem("bamboo-system-notifications:ZS001", "enabled");
  const show = vi.fn().mockResolvedValue(true);

  expect(await deliverUnreadBambooNotifications("ZS001", [message], show)).toBe(1);
  expect(await deliverUnreadBambooNotifications("ZS001", [message], show)).toBe(0);
  expect(show).toHaveBeenCalledTimes(1);
  expect(message.read_at).toBeNull();
});
