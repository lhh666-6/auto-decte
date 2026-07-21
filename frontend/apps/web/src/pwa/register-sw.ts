// @ts-ignore — virtual:pwa-register is provided by vite-plugin-pwa at build time
import { registerSW } from "virtual:pwa-register";

export interface PwaUpdateAvailableDetail {
  activate(): Promise<void>;
}

export function registerServiceWorker(): (() => void) | undefined {
  if (typeof window === "undefined") return undefined;

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
