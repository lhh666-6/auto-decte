import type { ReviewLease, WorkbenchDetail } from "@form-detection/api-client";

import type { QueueKey } from "./workbench-types";

interface WorkbenchActionBarProps {
  detail: WorkbenchDetail | null;
  lease: ReviewLease | null;
  loading: boolean;
  hasUnsavedEdits: boolean;
  warningCount: number;
  isCorrection: boolean;
  selectedQueue: QueueKey;
  onReturn: () => void;
  onVoid: () => void;
  onSaveDraft: () => void;
  onPrimary: () => void;
}

export function WorkbenchActionBar({
  detail,
  lease,
  loading,
  hasUnsavedEdits,
  warningCount,
  isCorrection,
  selectedQueue,
  onReturn,
  onVoid,
  onSaveDraft,
  onPrimary,
}: WorkbenchActionBarProps) {
  if (
    !detail ||
    detail.form.review_status === "NEEDS_CLASSIFICATION" ||
    detail.form.review_status === "RECAPTURE_REQUIRED"
  ) {
    return null;
  }

  return (
    <footer className="action-bar workbench-action-bar">
      <button type="button" className="button button-danger-secondary" disabled={!lease || loading} onClick={onReturn}>退回</button>
      <button type="button" className="button button-danger-secondary" disabled={!lease || loading} onClick={onVoid}>作废</button>
      {hasUnsavedEdits ? (
        <button type="button" className="button button-secondary" disabled={!lease || loading} onClick={onSaveDraft}>保存草稿</button>
      ) : null}
      <span className="action-hint">
        <strong>剩余问题 {warningCount}</strong>
        <span>{lease ? `你正在审核 · 有效至 ${new Date(lease.expires_at).toLocaleTimeString()}` : "请先开始审核"}</span>
      </span>
      <button
        type="button"
        className="button button-primary"
        disabled={!lease || loading || warningCount > 0 || (!isCorrection && selectedQueue !== "review") || (isCorrection && !hasUnsavedEdits)}
        title={warningCount > 0 ? "请先处理所有待确认字段" : undefined}
        onClick={onPrimary}
      >{isCorrection ? "保存本次修改" : "确认并下一张"}</button>
    </footer>
  );
}
