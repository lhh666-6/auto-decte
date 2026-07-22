/// <reference types="vite/client" />

// @ts-ignore — virtual:pwa-register is provided by vite-plugin-pwa at build time
import { registerSW } from "virtual:pwa-register";

import { isOwnedPwaCache, PWA_CACHE_ID } from "./pwa-cache-names";

export { PWA_CACHE_ID } from "./pwa-cache-names";

export interface PwaUpdateAvailableDetail {
  activate(): Promise<void>;
}

async function retireDevelopmentServiceWorker(): Promise<void> {
  const cleanup: Promise<unknown>[] = [];

  if ("serviceWorker" in navigator) {
    cleanup.push(
      navigator.serviceWorker.getRegistrations().then((registrations) => (
        Promise.all(registrations.map((registration) => registration.unregister()))
      )),
    );
  }

  if ("caches" in globalThis) {
    cleanup.push(
      caches.keys().then((cacheNames) => (
        Promise.all(cacheNames.filter(isOwnedPwaCache).map((cacheName) => caches.delete(cacheName)))
      )),
    );
  }

  await Promise.all(cleanup);
}

export function registerServiceWorker(): (() => void) | undefined {
  if (typeof window === "undefined") return undefined;

  if (import.meta.env.DEV) {
    void retireDevelopmentServiceWorker().catch((error: unknown) => {
      console.warn(`[PWA] ${PWA_CACHE_ID} development cleanup failed`, error);
    });
    return undefined;
  }

  let activate = async () => {};
  const updateSW = registerSW({
    onNeedRefresh() {
      window.dispatchEvent(new CustomEvent<PwaUpdateAvailableDetail>("pwa-update-available", {
        detail: { activate },
      }));
    },
    onOfflineReady() {
      console.info("[PWA] offline-ready");
    },
    onRegistered(registration: ServiceWorkerRegistration | undefined) {
      if (registration) {
        setInterval(() => { void registration.update(); }, 60 * 60 * 1000);
      }
    },
    onRegisterError(error: Error) {
      console.warn("[PWA] SW registration failed", error);
    },
  });
  activate = () => updateSW(true);
  return () => { void activate(); };
}
