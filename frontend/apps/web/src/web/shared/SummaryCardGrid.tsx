import type { ReactNode } from "react";

export interface SummaryCard {
  key: string;
  label: string;
  value: string | number;
  subtext?: string;
}

export function SummaryCardGrid({ cards }: { cards: SummaryCard[] }) {
  return (
    <div className="web-overview-cards">
      {cards.map((card) => (
        <div key={card.key} className="web-overview-card">
          <div className="web-overview-card-value">{card.value}</div>
          <div className="web-overview-card-label">{card.label}</div>
          {card.subtext && (
            <div style={{ color: "#8593a8", fontSize: 12 }}>{card.subtext}</div>
          )}
        </div>
      ))}
    </div>
  );
}

export function SummaryCardGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="web-overview-cards">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="web-overview-card" style={{ opacity: 0.5 }}>
          <div className="web-overview-card-value">—</div>
          <div className="web-overview-card-label">加载中...</div>
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div style={{ textAlign: "center", padding: "32px 16px", color: "#68778a" }}>
      <p>{message}</p>
      {action}
    </div>
  );
}

export function ErrorAlert({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="error-banner" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} style={{ border: "1px solid #e7b4b4", borderRadius: 4, padding: "4px 10px", background: "#fff", cursor: "pointer" }}>
          重试
        </button>
      )}
    </div>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header>
      <h1 style={{ margin: 0 }}>{title}</h1>
      {subtitle && <p style={{ margin: "4px 0 0", color: "#68778a" }}>{subtitle}</p>}
    </header>
  );
}
