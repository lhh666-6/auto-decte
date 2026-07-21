import { useCallback, useEffect, useState } from "react";

import { mobileApiClient, type MobileSubmissionListItem } from "@form-detection/api-client";

export function MobileSubmissionsPage() {
  const [submissions, setSubmissions] = useState<MobileSubmissionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await mobileApiClient.listSubmissions();
      setSubmissions(data.submissions);
    } catch {
      setError("无法加载提交记录，请检查网络后重试。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="mobile-page">
      <header className="mobile-page-header"><h2>我的提交</h2></header>
      {error && <div className="error-banner" role="alert"><p>{error}</p><button type="button" onClick={() => void load()}>重试</button></div>}
      {loading ? (
        <div className="mobile-loading">加载中…</div>
      ) : submissions.length === 0 ? (
        <div className="mobile-empty"><p>暂无提交记录</p></div>
      ) : (
        <ul className="mobile-submission-list">
          {submissions.map((submission) => (
            <li key={submission.submission_id} className="mobile-submission-card">
              <div><strong>电子表单回执</strong><span>{submission.form_id ?? "表单生成中"}</span></div>
              <div className="mobile-submission-meta">
                <span className="status-pill warning">{submission.status}</span>
                <small>{new Date(submission.submitted_at).toLocaleString("zh-CN")}</small>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
