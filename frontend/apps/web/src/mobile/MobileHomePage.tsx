import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { mobileApiClient, type MobileAvailableForm } from "@form-detection/api-client";
import { useMobileSession } from "./session/MobileSessionProvider";

/**
 * Mobile home page — shows worker identity, available forms, and quick actions.
 */
export function MobileHomePage() {
  const { sessionMetadata: session } = useMobileSession();
  const [forms, setForms] = useState<MobileAvailableForm[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    let cancelled = false;
    async function loadForms() {
      setLoading(true);
      setError("");
      try {
        const data = await mobileApiClient.getAvailableForms();
        if (!cancelled) {
          setForms(data.forms);
        }
      } catch {
        if (!cancelled) setError("无法加载可填写表单，请检查网络后重试。");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadForms();
    return () => { cancelled = true; };
  };

  useEffect(load, []);

  const hasRole = (role: string) => session?.roles?.includes(role) ?? false;

  if (loading) {
    return (
      <div className="mobile-page">
        <div className="mobile-loading">加载中…</div>
      </div>
    );
  }

  return (
    <div className="mobile-page mobile-home-page">
      <header className="mobile-home-greeting">
        <h2>你好，{session?.employee_name ?? "…"}</h2>
        <p>
          工号：{session?.employee_code} · {session?.team_name} · {session?.position}
        </p>
      </header>

      {error && <div className="error-banner" role="alert"><p>{error}</p><button type="button" onClick={load}>重试</button></div>}

      <section className="mobile-home-actions">
        <Link to="/mobile/record" className="mobile-home-card">
          <strong>记录我的工作</strong>
          <span>完成工序后主动记录</span>
        </Link>
        {hasRole("TEAM_LEADER") && (
          <Link to="/mobile/record/team-sheet-piece" className="mobile-home-card">
            <strong>记录班组工作</strong>
            <span>小组长集中填写</span>
          </Link>
        )}
      </section>

      {forms.length > 0 && (
        <section className="mobile-home-forms">
          <h3>可填写的记录类型</h3>
          <ul className="mobile-form-type-list">
            {forms.map((f) => (
              <li key={f.form_type}>
                <Link to={`/mobile/record?type=${f.form_type}`} className="mobile-form-type-item">
                  <strong>{f.title}</strong>
                  {f.allowed_processes && f.allowed_processes.length > 0 && (
                    <span>{f.allowed_processes.join("、")}</span>
                  )}
                  {f.modes && f.modes.includes("TEAM_LEADER_BATCH") && (
                    <span className="inline-success">含班组长模式</span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mobile-home-links">
        <Link to="/mobile/drafts" className="text-button">我的草稿</Link>
        <Link to="/mobile/outbox" className="text-button">待同步</Link>
        <Link to="/mobile/submissions" className="text-button">我的提交</Link>
      </section>
    </div>
  );
}
