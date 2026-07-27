import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { WebApiError } from "./api";
import { useWebSession } from "./WebSessionProvider";
import "./web-workspaces.css";

export function WebLoginPage() {
  const { status, session, login } = useWebSession();
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status === "loading") return <div role="status">正在验证登录状态…</div>;
  if (session) return <Navigate to={session.landing_path} replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const data = new FormData(event.currentTarget);
    try {
      const next = await login(
        String(data.get("employee_code") ?? "").trim(),
        String(data.get("pin") ?? ""),
      );
      navigate(next.landing_path, { replace: true });
    } catch (cause) {
      setError(
        cause instanceof WebApiError
          ? cause.problem.detail
          : "登录失败，请稍后重试。",
      );
      setPending(false);
    }
  }

  return (
    <div className="web-login-page">
      <form onSubmit={submit} className="web-login-form">
        <h1>工业工资表系统</h1>
        <p>统一管理工作区</p>
        {error && <div className="error-banner" role="alert">{error}</div>}
        <label>
          员工号
          <input name="employee_code" aria-label="员工号" autoComplete="username" required />
        </label>
        <label>
          密码
          <input name="pin" type="password" aria-label="密码" autoComplete="current-password" required />
        </label>
        <button type="submit" disabled={pending}>
          {pending ? "正在登录…" : "登录工作区"}
        </button>
      </form>
    </div>
  );
}
