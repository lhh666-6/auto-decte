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
  return (
    <footer className="action-bar workbench-action-bar">
      <button type="button" className="button button-danger-secondary" disabled={!detail || !lease || loading} onClick={onReturn}>退回</button>
      <button type="button" className="button button-danger-secondary" disabled={!detail || !lease || loading} onClick={onVoid}>作废</button>
      <button type="button" className="button button-secondary" disabled={!detail || !lease || loading || !hasUnsavedEdits} onClick={onSaveDraft}>保存草稿</button>
      <span className="action-hint">
        <strong>剩余问题 {warningCount}</strong>
        <span>{lease ? `租约到期 ${new Date(lease.expires_at).toLocaleTimeString()}` : "尚未获取审核锁"}</span>
      </span>
      <button
        type="button"
        className="button button-primary"
        disabled={!detail || !lease || loading || warningCount > 0 || (!isCorrection && selectedQueue !== "review")}
        title={warningCount > 0 ? "请先处理所有待确认字段" : undefined}
        onClick={onPrimary}
      >{isCorrection ? "保存更正" : "确认并下一张"}</button>
    </footer>
  );
}
