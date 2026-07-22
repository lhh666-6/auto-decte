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

export function MobileLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const session = useMobileSession();
  const [employeeCode, setEmployeeCode] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const login = useCallback(async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (!employeeCode.trim() || !pin.trim()) {
      setError("请输入工号和密码");
      return;
    }
    setLoading(true);
    try {
      await session.login(employeeCode.trim(), pin.trim(), getMobileDeviceId());
      const returnTo = safeReturnPath((location.state as { returnTo?: unknown } | null)?.returnTo);
      navigate(returnTo, { replace: true });
    } catch (cause) {
      setError(cause instanceof MobileApiError
        ? cause.problem.detail
        : "网络连接失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }, [employeeCode, location.state, navigate, pin, session]);

  return (
    <div className="mobile-page mobile-login-page bamboo-v3-login">
      <header className="mobile-login-header">
        <span className="bamboo-v3-login-mark" aria-hidden="true">竹</span>
        <span className="bamboo-v3-eyebrow">BAMBOO WORKFLOW</span>
        <h1>竹丝工序记录</h1>
        <p>工序流转与签字记录</p>
      </header>

      <form className="mobile-login-form" onSubmit={login}>
        {error && <div className="error-banner" role="alert">{error}</div>}
        <label>
          <span>工号</span>
          <input
            type="text"
            autoComplete="username"
            placeholder="请输入工号"
            value={employeeCode}
            onChange={(event) => setEmployeeCode(event.target.value)}
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
            onChange={(event) => setPin(event.target.value)}
            disabled={loading}
          />
        </label>
        <button type="submit" className="button button-primary mobile-login-button" disabled={loading}>
          {loading ? "登录中…" : "登录"}
        </button>
      </form>

      <footer className="mobile-login-footer"><small>仅限已授权人员使用</small></footer>
    </div>
  );
}
