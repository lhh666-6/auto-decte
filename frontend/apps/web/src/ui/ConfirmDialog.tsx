import type { ReactNode } from "react";
import { useEffect, useLayoutEffect, useRef } from "react";

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  cancelLabel = "取消停用",
  loading = false,
  confirmDisabled = false,
  children,
  onCancel,
  onConfirm,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  loading?: boolean;
  confirmDisabled?: boolean;
  children?: ReactNode;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const titleRef = useRef<HTMLHeadingElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const cancelRef = useRef(onCancel);
  cancelRef.current = onCancel;
  const titleId = useRef(`confirm-title-${Math.random().toString(36).slice(2)}`).current;
  const descriptionId = `${titleId}-description`;

  useLayoutEffect(() => {
    previousFocus.current = document.activeElement as HTMLElement | null;
    titleRef.current?.focus();
    return () => previousFocus.current?.focus();
  }, []);

  useEffect(() => {
    const cancelOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      cancelRef.current();
    };
    window.addEventListener("keydown", cancelOnEscape);
    return () => window.removeEventListener("keydown", cancelOnEscape);
  }, []);

  return (
    <div className="dialog-backdrop" role="presentation">
      <section
        className="review-action-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        <h2 id={titleId} ref={titleRef} tabIndex={-1}>{title}</h2>
        <p id={descriptionId}>{description}</p>
        {children}
        <div className="dialog-actions">
          <button type="button" className="button button-secondary" disabled={loading} onClick={onCancel}>{cancelLabel}</button>
          <button type="button" className="button button-danger" disabled={loading || confirmDisabled} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </section>
    </div>
  );
}
