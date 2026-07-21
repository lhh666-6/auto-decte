import { useCallback, useEffect, useState } from "react";

import { countAll } from "../mobile/storage/outbox";
import type { PwaUpdateAvailableDetail } from "./register-sw";

export function PwaUpdateNotice() {
  const [visible, setVisible] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [checking, setChecking] = useState(false);
  const [activate, setActivate] = useState<(() => Promise<void>) | null>(null);

  const refreshPending = useCallback(async () => {
    setChecking(true);
    try {
      setPendingCount(await countAll());
    } catch {
      setPendingCount(1);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    const show = (event: Event) => {
      const detail = (event as CustomEvent<PwaUpdateAvailableDetail>).detail;
      setActivate(() => detail?.activate ?? (async () => { window.location.reload(); }));
      setVisible(true);
      void refreshPending();
    };
    const outboxChanged = () => { if (visible) void refreshPending(); };
    window.addEventListener("pwa-update-available", show);
    window.addEventListener("mobile-outbox-changed", outboxChanged);
    return () => {
      window.removeEventListener("pwa-update-available", show);
      window.removeEventListener("mobile-outbox-changed", outboxChanged);
    };
  }, [refreshPending, visible]);

  if (!visible) return null;
  const blocked = checking || pendingCount > 0;

  return (
    <div className="pwa-update-banner" role="alert">
      <span>{pendingCount > 0
        ? `发现新版本；请先处理 ${pendingCount} 条未提交记录。`
        : "发现新版本，是否立即更新？"}</span>
      <div className="pwa-update-actions">
        {!blocked && (
          <button className="text-button" type="button" onClick={() => void activate?.()}>
            立即更新
          </button>
        )}
        <button className="text-button" type="button" onClick={() => setVisible(false)}>
          稍后更新
        </button>
      </div>
    </div>
  );
}
