import { useState } from "react";

export interface ImpactScope {
  factories: string[];
  affectedCount?: number;
  affectedRecords?: number | null;
}

export interface PreCheckResult {
  passed: boolean;
  errors: string[];
  warnings: string[];
}

export interface ReasonConfirmDialogProps {
  open: boolean;
  title: string;
  action: "APPROVE" | "REJECT";
  impactScope?: ImpactScope;
  preCheck?: PreCheckResult;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export function ReasonConfirmDialog({
  open,
  title,
  action,
  impactScope,
  preCheck,
  onConfirm,
  onCancel,
}: ReasonConfirmDialogProps) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  async function handleConfirm() {
    setSubmitting(true);
    try {
      onConfirm(reason);
    } finally {
      setSubmitting(false);
    }
  }

  const actionLabel = action === "APPROVE" ? "批准" : "驳回";
  const actionColor = action === "APPROVE" ? "#1e5a96" : "#9d2424";

  return (
    <div className="dialog-overlay" role="dialog" aria-modal="true" aria-label={title}>
      <div className="dialog-content">
        <h2>{title}</h2>

        {preCheck && (
          <div className="dialog-precheck">
            <h4>
              预检结果：
              <span className={preCheck.passed ? "precheck-passed" : "precheck-failed"}>
                {preCheck.passed ? "通过" : "未通过"}
              </span>
            </h4>
            {preCheck.errors.length > 0 && (
              <ul className="precheck-errors">
                {preCheck.errors.map((err, i) => (
                  <li key={`err-${i}`} className="precheck-error-item">{err}</li>
                ))}
              </ul>
            )}
            {preCheck.warnings.length > 0 && (
              <ul className="precheck-warnings">
                {preCheck.warnings.map((warn, i) => (
                  <li key={`warn-${i}`} className="precheck-warning-item">{warn}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {impactScope && (
          <div className="dialog-impact">
            <h4>影响范围</h4>
            {impactScope.factories.length > 0 && (
              <p>涉及工厂：{impactScope.factories.join("、")}</p>
            )}
            {impactScope.affectedCount !== undefined && (
              <p>受影响对象数：{impactScope.affectedCount}</p>
            )}
            {"affectedRecords" in impactScope && impactScope.affectedRecords !== undefined && (
              <p>受影响记录数：{impactScope.affectedRecords === null ? "暂无法计算" : impactScope.affectedRecords}</p>
            )}
          </div>
        )}

        <label className="dialog-reason-label">
          {actionLabel}原因（必填）
          <textarea
            className="dialog-reason-input"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={`请输入${actionLabel}原因...`}
            rows={3}
          />
        </label>

        <div className="dialog-actions">
          <button
            type="button"
            className="dialog-btn-cancel"
            onClick={onCancel}
            disabled={submitting}
          >
            取消
          </button>
          <button
            type="button"
            className="dialog-btn-confirm"
            style={{ background: actionColor }}
            onClick={() => void handleConfirm()}
            disabled={submitting || !reason.trim()}
          >
            {submitting ? "提交中..." : `确认${actionLabel}`}
          </button>
        </div>
      </div>
    </div>
  );
}
