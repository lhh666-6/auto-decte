import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useMobileSession } from "./session/MobileSessionProvider";
import { getPendingLogoutCount } from "./storage/session-cleanup";

export function MobileProfilePage() {
  const navigate = useNavigate();
  const { sessionMetadata: profile, logout } = useMobileSession();
  const [error, setError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    setError("");
    try {
      const pending = await getPendingLogoutCount(profile?.employee_code);
      if (pending > 0 && !window.confirm(
        `本机还有 ${pending} 条未提交记录。退出后会保留这些记录，确认继续退出吗？`,
      )) return;

      setLoggingOut(true);
      await logout();
      navigate("/mobile/login", { replace: true });
    } catch {
      setError("退出过程中发生错误，本机会话已清理，请重新登录。");
    } finally {
      setLoggingOut(false);
    }
  };

  if (!profile) return null;

  return (
    <div className="mobile-page">
      <header className="mobile-page-header">
        <h2>我的</h2>
      </header>
      <section className="mobile-profile-info">
        <div className="mobile-profile-avatar">{profile.employee_name.charAt(0)}</div>
        <div>
          <strong>{profile.employee_name}</strong>
          <span>工号：{profile.employee_code}</span>
          <span>{profile.team_name} · {profile.position}</span>
        </div>
      </section>
      <section className="mobile-profile-actions">
        {error && <div className="error-banner" role="alert">{error}</div>}
        <button type="button" className="button button-secondary" onClick={handleLogout} disabled={loggingOut}>
          {loggingOut ? "退出中…" : "退出登录"}
        </button>
      </section>
    </div>
  );
}
