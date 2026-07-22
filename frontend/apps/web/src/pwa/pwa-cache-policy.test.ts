// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runtimePolicyForPath } from "./cache-policy";

const pwaMocks = vi.hoisted(() => ({
  registerSW: vi.fn(),
  updateSW: vi.fn(),
}));

vi.mock("virtual:pwa-register", () => ({
  registerSW: pwaMocks.registerSW,
}));

import { PWA_CACHE_ID, registerServiceWorker } from "./register-sw";

function setServiceWorkers(getRegistrations: ReturnType<typeof vi.fn>) {
  Object.defineProperty(window.navigator, "serviceWorker", {
    configurable: true,
    value: { getRegistrations },
  });
}

function setCacheStorage(keys: string[], deleteCache: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("caches", {
    keys: vi.fn().mockResolvedValue(keys),
    delete: deleteCache,
  });
}

describe("PWA lifecycle policy", () => {
  beforeEach(() => {
    pwaMocks.updateSW.mockReset();
    pwaMocks.registerSW.mockReset().mockReturnValue(pwaMocks.updateSW);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("unregisters existing service workers instead of registering one in development", async () => {
    vi.stubEnv("DEV", true);
    const unregisterFirst = vi.fn().mockResolvedValue(true);
    const unregisterSecond = vi.fn().mockResolvedValue(true);
    const getRegistrations = vi.fn().mockResolvedValue([
      { unregister: unregisterFirst },
      { unregister: unregisterSecond },
    ]);
    setServiceWorkers(getRegistrations);
    setCacheStorage([], vi.fn().mockResolvedValue(true));

    expect(registerServiceWorker()).toBeUndefined();

    await vi.waitFor(() => {
      expect(unregisterFirst).toHaveBeenCalledOnce();
      expect(unregisterSecond).toHaveBeenCalledOnce();
    });
    expect(pwaMocks.registerSW).not.toHaveBeenCalled();
  });

  it("deletes only caches owned by this application during development cleanup", async () => {
    vi.stubEnv("DEV", true);
    setServiceWorkers(vi.fn().mockResolvedValue([]));
    const deleteCache = vi.fn().mockResolvedValue(true);
    setCacheStorage([
      "form-detection-web-v1-precache",
      "form-detection-web-v2-runtime",
      `${PWA_CACHE_ID}-precache`,
      `${PWA_CACHE_ID}-runtime`,
      "shared-cache",
      `another-app-${PWA_CACHE_ID}`,
    ], deleteCache);

    registerServiceWorker();

    await vi.waitFor(() => {
      expect(deleteCache).toHaveBeenCalledTimes(4);
    });
    expect(deleteCache).toHaveBeenNthCalledWith(1, "form-detection-web-v1-precache");
    expect(deleteCache).toHaveBeenNthCalledWith(2, "form-detection-web-v2-runtime");
    expect(deleteCache).toHaveBeenNthCalledWith(3, `${PWA_CACHE_ID}-precache`);
    expect(deleteCache).toHaveBeenNthCalledWith(4, `${PWA_CACHE_ID}-runtime`);
  });

  it("registers in production and preserves prompt-based activation", async () => {
    vi.stubEnv("DEV", false);
    const getRegistrations = vi.fn();
    setServiceWorkers(getRegistrations);
    const deleteCache = vi.fn();
    setCacheStorage([], deleteCache);
    const updateAvailable = new Promise<CustomEvent>((resolve) => {
      window.addEventListener("pwa-update-available", (event) => resolve(event as CustomEvent), { once: true });
    });

    const activate = registerServiceWorker();

    expect(pwaMocks.registerSW).toHaveBeenCalledOnce();
    expect(getRegistrations).not.toHaveBeenCalled();
    expect(deleteCache).not.toHaveBeenCalled();
    const options = pwaMocks.registerSW.mock.calls[0][0];
    options.onNeedRefresh();
    const event = await updateAvailable;
    await event.detail.activate();
    expect(pwaMocks.updateSW).toHaveBeenCalledWith(true);

    activate?.();
    expect(pwaMocks.updateSW).toHaveBeenCalledTimes(2);
  });
});

describe("PWA private-data cache policy", () => {
  it.each([
    "/api/v1/mobile/auth/session",
    "/api/v1/mobile/submissions",
    "/api/v1/mobile/drafts",
    "/api/v1/mobile/context",
    "/api/v1/mobile/active-resources",
    "/api/v1/mobile/available-forms",
    "/api/v1/evidence/file-1",
    "/api/v1/exports/batch-1/download",
    "/downloads/report.xlsx",
    "/evidence/photo.jpg",
  ])("uses NetworkOnly for %s", (path) => {
    expect(runtimePolicyForPath(path)).toBe("NetworkOnly");
  });

  it("does not grant a cache strategy to authenticated reference data", () => {
    expect(runtimePolicyForPath("/api/v1/mobile/options/employees")).toBe("NetworkOnly");
    expect(runtimePolicyForPath("/api/v1/mobile/form-schemas/FORM-A")).toBe("NetworkOnly");
  });
});
