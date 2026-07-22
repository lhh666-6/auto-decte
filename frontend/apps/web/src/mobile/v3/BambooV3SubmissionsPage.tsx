import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { mobileApiClient, type MobileSubmissionListItem } from "@form-detection/api-client";

import { getMobileDeviceId } from "../device";
import { useMobileSession } from "../session/MobileSessionProvider";
import { listDrafts } from "../storage/drafts";
import { countAll } from "../storage/outbox";

export function BambooV3SubmissionsPage() {
  const { sessionMetadata } = useMobileSession();
  const [submissions, setSubmissions] = useState<MobileSubmissionListItem[]>([]);
  const [draftCount, setDraftCount] = useState(0);
  const [outboxCount, setOutboxCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!sessionMetadata) return;
    setLoading(true);
    setError("");
    try {
      const [remote, drafts, queued] = await Promise.all([
        mobileApiClient.listSubmissions(),
        listDrafts(sessionMetadata.employee_code, getMobileDeviceId()),
        countAll(),
      ]);
      setSubmissions(remote.submissions);
      setDraftCount(drafts.length);
      setOutboxCount(queued);
    } catch {
      setError("无法加载提交记录，本地数据仍会保留。");
    } finally {
      setLoading(false);
    }
  }, [sessionMetadata]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const refresh = () => { void load(); };
    window.addEventListener("mobile-outbox-changed", refresh);
    return () => window.removeEventListener("mobile-outbox-changed", refresh);
  }, [load]);

  return (
    <div className="page bamboo-v3-submissions">
      <h2 className="visually-hidden">提交记录</h2>
      <section className="section">
        <div className="section-head">
          <div className="section-title">我的提交</div>
          <div className="section-note">{submissions.length} 条</div>
        </div>
        <div className="stats submissions-stats" aria-label="本机提交概况">
          <div className="stat"><span className="visually-hidden">本地草稿</span><b>{draftCount}</b><span>我的草稿</span></div>
          <div className="stat"><span className="visually-hidden">待同步</span><b>{outboxCount}</b><span>同步队列</span></div>
          <div className="stat"><span className="visually-hidden">已提交</span><b>{submissions.length}</b><span>我的提交</span></div>
        </div>
      </section>

      {error && <div className="banner danger" role="alert">{error}<button type="button" className="btn small secondary" onClick={() => void load()}>重试</button></div>}

      {loading ? (
        <div className="mobile-loading">加载中…</div>
      ) : submissions.length === 0 ? (
        <div className="card empty">
          <h3>暂无提交记录</h3>
          <p>完成工序签字后，这里会显示本人提交与后续流转状态。</p>
          <Link className="btn primary full" to="/mobile/work">记录我的工作</Link>
        </div>
      ) : (
        <div className="list">
          {submissions.map((item) => (
            <article className="record-card" key={item.submission_id}>
              <div className="record-top">
                <div>
                  <div className="record-no">{item.form_id || item.submission_id}</div>
                  <span className="visually-hidden">{item.submission_id}</span>
                  <div className="record-meta">提交单号 {item.submission_id} · {formatTime(item.submitted_at)}</div>
                </div>
                <span className={`chip ${chipClass(item.status)}`}>{submissionStatus(item.status)}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function chipClass(status: string): string {
  if (["ACCEPTED", "COMPLETED", "APPROVED"].includes(status)) return "ok";
  return "wait";
}

function submissionStatus(status: string): string {
  return ({ ACCEPTED: "已接收", COMPLETED: "已完成", APPROVED: "已通过", PENDING: "等待中" } as Record<string, string>)[status] ?? status;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
