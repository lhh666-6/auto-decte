import { useEffect, useState } from "react";

import { getOverview } from "./api";
import type { WorkspaceOverview, WorkspaceRole } from "./types";

const SEGMENT: Record<WorkspaceRole, string> = {
  ADMIN: "admin",
  FINANCE: "finance",
  PLANT_MANAGER: "plant",
};

export function WorkspaceOverviewPage({ workspace }: { workspace: WorkspaceRole }) {
  const [overview, setOverview] = useState<WorkspaceOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

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
        {overview.cards.map((card) => (
          <article key={card.key} className="web-overview-card">
            <span className="web-overview-card-value">{card.value}</span>
            <span className="web-overview-card-label">{card.label}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
