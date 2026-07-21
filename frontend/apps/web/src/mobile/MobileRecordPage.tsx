import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { mobileApiClient, type MobileAvailableForm } from "@form-detection/api-client";

/**
 * Mobile record-type selection page.
 * Worker picks which kind of work record to create.
 */
export function MobileRecordPage() {
  const [searchParams] = useSearchParams();
  const preselectedType = searchParams.get("type");
  const [forms, setForms] = useState<MobileAvailableForm[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    let cancelled = false;
    setLoading(true);
    setError("");
    mobileApiClient.getAvailableForms()
      .then((data) => {
        if (!cancelled) setForms(data.forms);
      })
      .catch(() => { if (!cancelled) setError("无法加载记录类型，请检查网络后重试。"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  };

  useEffect(load, []);

  // Route to the correct form page based on form_type
  function formRoute(formType: string): string {
    switch (formType) {
      case "BAMBOO_PROCESS_RECORD":
        return "/mobile/record/bamboo-process";
      case "SHEET_PIECE_MEASUREMENT":
        return "/mobile/record/sheet-piece";
      case "TEAM_SHEET_PIECE_MEASUREMENT":
        return "/mobile/record/team-sheet-piece";
      default:
        return `/mobile/forms/${formType}`;
    }
  }

  if (loading) {
    return <div className="mobile-page"><div className="mobile-loading">加载中…</div></div>;
  }

  const filtered = preselectedType
    ? forms.filter((f) => f.form_type === preselectedType)
    : forms;

  return (
    <div className="mobile-page">
      <header className="mobile-page-header">
        <Link to="/mobile/home" className="text-button">← 返回</Link>
        <h2>选择记录类型</h2>
      </header>
      {error && <div className="error-banner" role="alert"><p>{error}</p><button type="button" onClick={load}>重试</button></div>}
      {filtered.length === 0 ? (
        <div className="mobile-empty">
          <p>当前没有可填写的记录类型</p>
          <Link to="/mobile/home" className="button button-secondary">返回首页</Link>
        </div>
      ) : (
        <ul className="mobile-record-type-list">
          {filtered.map((f) => (
            <li key={f.form_type}>
              <Link to={formRoute(f.form_type)} className="mobile-record-type-card">
                <strong>{f.title}</strong>
                {f.allowed_processes && f.allowed_processes.length > 0 && (
                  <span>可填写工序：{f.allowed_processes.join("、")}</span>
                )}
                {f.modes && f.modes.includes("TEAM_LEADER_BATCH") && (
                  <span className="inline-success">支持班组长批量填写</span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
