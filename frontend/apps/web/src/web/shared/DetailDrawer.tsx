import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

export interface DetailDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  "data-testid"?: string;
}

export function DetailDrawer({ open, onClose, title, children, "data-testid": testId }: DetailDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  /** Save trigger element and move focus into drawer on open. */
  useEffect(() => {
    if (open) {
      triggerRef.current = document.activeElement as HTMLElement;
      // Small delay to allow the DOM to render before focusing
      const raf = requestAnimationFrame(() => {
        closeButtonRef.current?.focus();
      });
      return () => cancelAnimationFrame(raf);
    } else {
      // Return focus to trigger element on close
      triggerRef.current?.focus();
      triggerRef.current = null;
    }
    return undefined;
  }, [open]);

  /** Close on Escape key */
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="detail-drawer-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      data-testid={testId}
      ref={drawerRef}
    >
      <div className="detail-drawer">
        <div className="detail-drawer-header">
          <h2>{title}</h2>
          <button
            ref={closeButtonRef}
            type="button"
            className="detail-drawer-close"
            onClick={onClose}
            aria-label={`关闭${title}`}
            data-testid={testId ? `${testId}-close` : undefined}
          >
            &#x2715;
          </button>
        </div>
        <div className="detail-drawer-body">
          {children}
        </div>
      </div>
    </div>
  );
}

export function DetailField({ label, value, testId }: { label: string; value?: string; testId?: string }) {
  return (
    <div className="detail-field" data-testid={testId}>
      <span className="detail-field-label">{label}</span>
      <span className="detail-field-value">{value ?? "—"}</span>
    </div>
  );
}
