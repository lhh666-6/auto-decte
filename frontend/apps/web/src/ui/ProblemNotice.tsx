import type { ReactNode } from "react";

import { TraceDetails } from "./TraceDetails";

export function ProblemNotice({
  title,
  reason,
  actionLabel,
  onAction,
  code,
}: {
  title: string;
  reason: ReactNode;
  actionLabel: string;
  onAction: () => void;
  code?: string | null;
}) {
  return (
    <section className="error-banner problem-notice" role="alert">
      <div>
        <h2>{title}</h2>
        <p>{reason}</p>
        {code ? <TraceDetails items={[{ label: "问题代码", value: code }]} /> : null}
      </div>
      <button type="button" className="button button-secondary" onClick={onAction}>{actionLabel}</button>
    </section>
  );
}
