import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useWebSession } from "./WebSessionProvider";
import type { WorkspaceRole } from "./types";

export function RequireWebSession({
  workspace,
  children,
}: {
  workspace: WorkspaceRole;
  children: ReactNode;
}) {
  const { status, session } = useWebSession();

  if (status === "loading") return <div role="status">正在验证登录状态…</div>;
  if (status === "error" || !session) return <Navigate to="/login" replace />;

  const permitted = session.workspace_roles.includes("ADMIN")
    || session.workspace_roles.includes(workspace);
  if (!permitted) return <Navigate to={session.landing_path} replace />;

  return <>{children}</>;
}
