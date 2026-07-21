import { useCallback, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { MobileApiError } from "@form-detection/api-client";

import { getMobileDeviceId } from "./device";
import { useMobileSession } from "./session/MobileSessionProvider";

function safeReturnPath(value: unknown): string {
  return typeof value === "string" && value.startsWith("/mobile/") && !value.startsWith("//")
    ? value
    : "/mobile/home";
}

/**
 * Mobile login page — worker ID + PIN/password.
 * After successful login, redirects to /mobile/home.
 */
export function MobileLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const session = useMobileSession();
  const [employeeCode, setEmployeeCode] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const login = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError("");
      if (!employeeCode.trim() || !pin.trim()) {
        setError("请输入工号和密码");
        return;
      }
      setLoading(true);
      try {
        await session.login(employeeCode.trim(), pin.trim(), getMobileDeviceId());
        const returnTo = safeReturnPath(
          (location.state as { returnTo?: unknown } | null)?.returnTo,
        );
        navigate(returnTo, { replace: true });
      } catch (cause) {
        setError(cause instanceof MobileApiError
          ? cause.problem.detail
          : "网络连接失败，请稍后重试");
      } finally {
        setLoading(false);
      }
    },
    [employeeCode, location.state, navigate, pin, session],
  );

  return (
    <div className="mobile-page mobile-login-page">
      <header className="mobile-login-header">
        <h1>工业工资表系统</h1>
        <p>请使用工号和密码登录</p>
      </header>
      <form className="mobile-login-form" onSubmit={login}>
        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}
        <label>
          <span>工号</span>
          <input
            type="text"
            inputMode="numeric"
            autoComplete="username"
            placeholder="请输入工号"
            value={employeeCode}
            onChange={(e) => setEmployeeCode(e.target.value)}
            disabled={loading}
          />
        </label>
        <label>
          <span>密码 / PIN</span>
          <input
            type="password"
            inputMode="numeric"
            autoComplete="current-password"
            placeholder="请输入密码或 PIN"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            disabled={loading}
          />
        </label>
        <button type="submit" className="button button-primary mobile-login-button" disabled={loading}>
          {loading ? "登录中…" : "登录"}
        </button>
      </form>
      <footer className="mobile-login-footer">
        <small>试点版本 · 仅限授权人员使用</small>
      </footer>
    </div>
  );
}
