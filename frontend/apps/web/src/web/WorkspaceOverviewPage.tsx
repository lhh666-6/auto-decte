import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getOverview } from "./api";
import type { WorkspaceOverview, WorkspaceRole } from "./types";

const SEGMENT: Record<WorkspaceRole, string> = {
  ADMIN: "admin",
  FINANCE: "finance",
  PLANT_MANAGER: "plant",
};

const CARD_ROUTES: Record<string, string> = {
  pending_form_approvals: "/admin/form-approvals",
  pending_workflow_approvals: "/admin/workflow-approvals",
  pending_payroll_approvals: "/admin/payroll-approvals",
  form_approvals: "/admin/form-approvals",
  workflow_approvals: "/admin/workflow-approvals",
  payroll_approvals: "/admin/payroll-approvals",
};

export function WorkspaceOverviewPage({ workspace }: { workspace: WorkspaceRole }) {
  const [overview, setOverview] = useState<WorkspaceOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    getOverview(SEGMENT[workspace])
      .then((data) => {
        if (active) setOverview(data);
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "概览加载失败");
      });
    return () => {
      active = false;
    };
  }, [workspace]);

  if (error) return <div role="alert">{error}</div>;
  if (!overview) return <div role="status">正在加载概览…</div>;

  return (
    <section className="web-overview-page">
      <h1>{overview.title}</h1>
      {overview.factory_name && <p>{overview.factory_name}</p>}
      <div className="web-overview-cards">
        {overview.cards.map((card) => {
          const route = CARD_ROUTES[card.key];
          const isClickable = !!route;
          return (
            <article
              key={card.key}
              className={`web-overview-card ${isClickable ? "web-overview-card-clickable" : ""}`}
              onClick={isClickable ? () => navigate(route) : undefined}
              style={isClickable ? { cursor: "pointer" } : undefined}
              role={isClickable ? "button" : undefined}
              tabIndex={isClickable ? 0 : undefined}
              onKeyDown={isClickable ? (e) => { if (e.key === "Enter" || e.key === " ") navigate(route); } : undefined}
            >
              <span className="web-overview-card-value">{card.value}</span>
              <span className="web-overview-card-label">{card.label}</span>
            </article>
          );
        })}
      </div>
    </section>
  );
}
