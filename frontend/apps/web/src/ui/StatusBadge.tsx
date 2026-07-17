import type { ReactNode } from "react";

export type StatusTone = "success" | "warning" | "danger" | "neutral";

const MEANING: Record<StatusTone, string> = {
  success: "成功",
  warning: "需要注意",
  danger: "失败",
  neutral: "一般",
};

const SYMBOL: Record<StatusTone, string> = {
  success: "✓",
  warning: "!",
  danger: "×",
  neutral: "•",
};

export function StatusBadge({ tone, children }: { tone: StatusTone; children: ReactNode }) {
  const label = typeof children === "string" ? children : "当前";
  const meaning = `${MEANING[tone]}状态`;
  return (
    <span
      className="status-badge"
      data-tone={tone}
      role="status"
      aria-label={`${label}，${meaning}`}
    >
      <span aria-hidden="true">{SYMBOL[tone]}</span>
      <span>{children}</span>
      <span className="visually-hidden">{meaning}</span>
    </span>
  );
}
