import { useCallback, useEffect, useState } from "react";

type InstallPromptEvent = Event & {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

let deferredPrompt: InstallPromptEvent | null = null;
let installedByPrompt = false;
const listeners = new Set<() => void>();

function notify(): void { listeners.forEach((listener) => listener()); }
function standalone(): boolean {
  return typeof window !== "undefined" && (Boolean(window.matchMedia?.("(display-mode: standalone)").matches) || Boolean((navigator as Navigator & { standalone?: boolean }).standalone));
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event as InstallPromptEvent;
    notify();
  });
  window.addEventListener("appinstalled", () => { deferredPrompt = null; installedByPrompt = true; notify(); });
}

export function usePwaInstall() {
  const [, refresh] = useState(0);
  useEffect(() => {
    const listener = () => refresh((value) => value + 1);
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  }, []);

  const install = useCallback(async (): Promise<"installed" | "dismissed" | "unavailable"> => {
    if (standalone() || installedByPrompt) return "installed";
    const prompt = deferredPrompt;
    if (!prompt) return "unavailable";
    await prompt.prompt();
    const result = await prompt.userChoice;
    if (result.outcome === "accepted") {
      deferredPrompt = null;
      installedByPrompt = true;
    }
    notify();
    return result.outcome === "accepted" ? "installed" : "dismissed";
  }, []);

  return { installed: standalone() || installedByPrompt, canInstall: deferredPrompt !== null, install };
}
