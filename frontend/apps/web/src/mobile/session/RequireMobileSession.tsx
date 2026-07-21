import { Navigate, Outlet, useLocation } from "react-router-dom";

import { MobileApiError } from "@form-detection/api-client";

import { useMobileSession } from "./MobileSessionProvider";

function safeReturnPath(path: string): string {
  return path.startsWith("/mobile/") && !path.startsWith("//")
    ? path
    : "/mobile/home";
}

export function RequireMobileSession() {
  const { status, refreshSession, error } = useMobileSession();
  const location = useLocation();

  if (status === "loading") {
    return <div className="mobile-loading" role="status">正在验证登录状态…</div>;
  }
  if (status === "anonymous") {
    const returnTo = safeReturnPath(`${location.pathname}${location.search}${location.hash}`);
    return <Navigate to="/mobile/login" replace state={{ returnTo }} />;
  }
  if (status === "error") {
    return (
      <section className="mobile-page" role="alert">
        <p>暂时无法验证登录状态，请检查网络后重试。</p>
        {error instanceof MobileApiError && error.problem.request_id && (
          <small>请求编号：{error.problem.request_id}</small>
        )}
        <button type="button" className="button button-primary" onClick={() => void refreshSession()}>
          重试
        </button>
      </section>
    );
  }
  return <Outlet />;
}
