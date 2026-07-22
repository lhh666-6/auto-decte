import { useCallback, useEffect, useState } from "react";

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

  const waiting = submissions.filter((item) => !["ACCEPTED", "COMPLETED", "APPROVED"].includes(item.status));
  const completed = submissions.filter((item) => !waiting.includes(item));

  return (
    <div className="mobile-page bamboo-v3-page bamboo-v3-submissions">
      <header className="bamboo-v3-page-header">
        <p>查看本人提交与流转状态</p>
        <h2>提交记录</h2>
      </header>

      <section className="bamboo-v3-counter-grid" aria-label="本机提交概况">
        <div><span>本地草稿</span><strong>{draftCount}</strong></div>
        <div><span>待同步</span><strong>{outboxCount}</strong></div>
        <div><span>已提交</span><strong>{submissions.length}</strong></div>
      </section>

      {error && <div className="error-banner" role="alert">{error}<button type="button" onClick={() => void load()}>重试</button></div>}
      {loading ? <div className="mobile-loading">加载中…</div> : (
        <div className="bamboo-v3-submission-groups">
          <SubmissionGroup title="等待中" items={waiting} empty="暂无等待中的记录" />
          <SubmissionGroup title="已完成" items={completed} empty="暂无已完成的记录" />
        </div>
      )}
    </div>
  );
}

function SubmissionGroup({ title, items, empty }: { title: string; items: MobileSubmissionListItem[]; empty: string }) {
  return (
    <section className="bamboo-v3-list-section">
      <h3>{title}<span>{items.length}</span></h3>
      {items.length === 0 ? <p className="bamboo-v3-empty-copy">{empty}</p> : (
        <ul>
          {items.map((item) => (
            <li className="bamboo-v3-submission-card" key={item.submission_id}>
              <div><strong>{item.submission_id}</strong><span>{item.form_id || "竹丝工序记录"}</span></div>
              <div><span className="bamboo-v3-status-pill">{submissionStatus(item.status)}</span><time>{formatTime(item.submitted_at)}</time></div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function submissionStatus(status: string): string {
  return ({ ACCEPTED: "已接收", COMPLETED: "已完成", APPROVED: "已通过", PENDING: "等待中" } as Record<string, string>)[status] ?? status;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
