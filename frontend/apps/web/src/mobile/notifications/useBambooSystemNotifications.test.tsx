// @vitest-environment jsdom

import { render, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ listBambooNotifications: vi.fn() }));

vi.mock("@form-detection/api-client", () => ({
  mobileApiClient: { listBambooNotifications: mocks.listBambooNotifications },
}));

import { useBambooSystemNotifications } from "./useBambooSystemNotifications";

function Probe() {
  useBambooSystemNotifications("ZS001", true);
  return null;
}

beforeEach(() => {
  localStorage.clear();
  mocks.listBambooNotifications.mockReset();
});

it("polls durable messages after opt-in and mirrors an unread item", async () => {
  const shown = vi.fn();
  class NotificationMock {
    static permission = "granted";
    static requestPermission = vi.fn();
    constructor(title: string, options?: NotificationOptions) { shown(title, options); }
  }
  Object.defineProperty(window, "Notification", { configurable: true, value: NotificationMock });
  localStorage.setItem("bamboo-system-notifications:ZS001", "enabled");
  mocks.listBambooNotifications.mockResolvedValue({ items: [{
    notification_id: "NOTICE-1", category: "INSPECTION", title: "检测已终止",
    body: "厂长已提前签字", link: null, payload: {}, read_at: null,
    created_at: "2026-07-23T03:00:00Z",
  }] });

  render(<Probe />);
  await waitFor(() => expect(mocks.listBambooNotifications).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(shown).toHaveBeenCalledWith("检测已终止", expect.objectContaining({ tag: "bamboo-NOTICE-1" })));
});
