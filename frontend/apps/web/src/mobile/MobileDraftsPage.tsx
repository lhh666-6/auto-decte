import { useCallback, useEffect, useState } from "react";

import { getMobileDeviceId } from "./device";
import { useMobileSession } from "./session/MobileSessionProvider";
import { deleteDraft, listDrafts, type StoredDraft } from "./storage/drafts";

const FORM_LABELS: Record<string, string> = {
  BAMBOO_PROCESS_RECORD: "竹丝工序记录",
  SHEET_PIECE_MEASUREMENT: "配片工作记录",
  TEAM_SHEET_PIECE_MEASUREMENT: "班组配片记录",
};

export function MobileDraftsPage() {
  const { sessionMetadata } = useMobileSession();
  const [drafts, setDrafts] = useState<StoredDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!sessionMetadata) return;
    setLoading(true);
    setError("");
    try {
      setDrafts(await listDrafts(sessionMetadata.employee_code, getMobileDeviceId()));
    } catch {
      setError("无法读取本机草稿，请重试。");
    } finally {
      setLoading(false);
    }
  }, [sessionMetadata]);

  useEffect(() => { void load(); }, [load]);

  const discard = async (draft: StoredDraft) => {
    if (!window.confirm("确认删除这条本机草稿吗？删除后无法恢复。")) return;
    try {
      await deleteDraft(draft.owner, draft.deviceId, draft.localDraftId);
      await load();
    } catch {
      setError("删除草稿失败，请重试。");
    }
  };

  return (
    <div className="mobile-page">
      <header className="mobile-page-header"><h2>我的草稿</h2></header>
      {error && <div className="error-banner" role="alert"><p>{error}</p><button type="button" onClick={() => void load()}>重试</button></div>}
      {loading ? (
        <div className="mobile-loading">加载中…</div>
      ) : drafts.length === 0 ? (
        <div className="mobile-empty"><p>暂无草稿</p></div>
      ) : (
        <ul className="mobile-draft-list">
          {drafts.map((draft) => (
            <li key={draft.storageKey} className="mobile-draft-card">
              <strong>{FORM_LABELS[draft.formType] ?? draft.formType}</strong>
              <span>更新于 {new Date(draft.updatedAt).toLocaleString("zh-CN")}</span>
              <button type="button" className="text-button" onClick={() => void discard(draft)}>删除草稿</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
