export type StatusVariant =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "ACTIVE"
  | "INACTIVE"
  | "ERROR"
  | "CORRECTED"
  | "NEED_REEXPORT"
  | "RETIRED"
  | "CONFLICT"
  | string;

/** §8.11 — 完整状态映射：展示文本、颜色、语义描述 */
const STATUS_META: Record<string, { display: string; color: string; bg: string; description: string }> = {
  DRAFT: {
    display: "草稿",
    color: "#596579",
    bg: "#e8ecf1",
    description: "尚未提交的草稿状态",
  },
  PENDING_APPROVAL: {
    display: "待审批",
    color: "#155eef",
    bg: "#e0ecfe",
    description: "已提交，等待审批",
  },
  APPROVED: {
    display: "已批准",
    color: "#1a6b3c",
    bg: "#d4edda",
    description: "审批已通过",
  },
  REJECTED: {
    display: "已驳回",
    color: "#9d2424",
    bg: "#fce4e4",
    description: "审批已驳回",
  },
  ACTIVE: {
    display: "正式",
    color: "#1a6b3c",
    bg: "#d4edda",
    description: "正式有效状态",
  },
  INACTIVE: {
    display: "已停用",
    color: "#596579",
    bg: "#e8ecf1",
    description: "已停用",
  },
  ERROR: {
    display: "异常",
    color: "#d97706",
    bg: "#fff7ed",
    description: "数据存在异常",
  },
  CORRECTED: {
    display: "已更正",
    color: "#3b5998",
    bg: "#e8edf5",
    description: "已更正",
  },
  NEED_REEXPORT: {
    display: "需重导",
    color: "#d97706",
    bg: "#fff7ed",
    description: "需要重新导出",
  },
  RETIRED: {
    display: "已退役",
    color: "#596579",
    bg: "#e8ecf1",
    description: "已退役",
  },
  CONFLICT: {
    display: "数据已更新",
    color: "#9d2424",
    bg: "#fce4e4",
    description: "数据已更新（冲突）",
  },
  REPLACED: {
    display: "已替换",
    color: "#8a6300",
    bg: "#fff3cd",
    description: "已被新版本替换",
  },
  AVAILABLE: {
    display: "可下载",
    color: "#1a6b3c",
    bg: "#d4edda",
    description: "可下载",
  },
  CONFIRMED: {
    display: "已确认",
    color: "#1a6b3c",
    bg: "#d4edda",
    description: "已确认",
  },
  SUBMITTED: {
    display: "已提交",
    color: "#155eef",
    bg: "#e0ecfe",
    description: "已提交",
  },
  FAILED: {
    display: "失败",
    color: "#9d2424",
    bg: "#fce4e4",
    description: "处理失败",
  },
  COMPLETED: {
    display: "已完成",
    color: "#1a6b3c",
    bg: "#d4edda",
    description: "已完成",
  },
  EXPIRED: {
    display: "已过期",
    color: "#596579",
    bg: "#e8ecf1",
    description: "已过期",
  },
  SUPERSEDED: {
    display: "已被替代",
    color: "#8a6300",
    bg: "#fff3cd",
    description: "已被新版本替代",
  },
  OPEN: {
    display: "待处理",
    color: "#155eef",
    bg: "#e0ecfe",
    description: "待处理",
  },
  CLAIMED: {
    display: "处理中",
    color: "#d97706",
    bg: "#fff7ed",
    description: "已被认领处理中",
  },
  EARLY_TERMINATED: {
    display: "已终止",
    color: "#596579",
    bg: "#e8ecf1",
    description: "已提前终止",
  },
  RETURNED: {
    display: "已退回",
    color: "#9d2424",
    bg: "#fce4e4",
    description: "已退回",
  },
  OVERRULED: {
    display: "已驳回",
    color: "#9d2424",
    bg: "#fce4e4",
    description: "已驳回",
  },
  CLOSED: {
    display: "已关闭",
    color: "#596579",
    bg: "#e8ecf1",
    description: "已关闭",
  },
  APPEAL_SUBMITTED: {
    display: "上诉待审批",
    color: "#d97706",
    bg: "#fff7ed",
    description: "上诉待审批",
  },
  APPEAL_APPROVED: {
    display: "上诉已批准",
    color: "#1a6b3c",
    bg: "#d4edda",
    description: "上诉已批准",
  },
  APPEAL_REJECTED: {
    display: "上诉已驳回",
    color: "#9d2424",
    bg: "#fce4e4",
    description: "上诉已驳回",
  },
};

/** 状态指示灯符号（辅助颜色传达，确保颜色不是唯一的信息传达方式） */
const STATUS_ICON: Record<string, string> = {
  DRAFT: "○",
  PENDING_APPROVAL: "◆",
  APPROVED: "✓",
  REJECTED: "✗",
  ACTIVE: "●",
  INACTIVE: "○",
  ERROR: "⚠",
  CORRECTED: "→",
  NEED_REEXPORT: "↺",
  RETIRED: "□",
  CONFLICT: "✗",
  REPLACED: "→",
  AVAILABLE: "✓",
  CONFIRMED: "✓",
  SUBMITTED: "◆",
  FAILED: "✗",
  COMPLETED: "✓",
  EXPIRED: "✗",
  SUPERSEDED: "↺",
  OPEN: "○",
  CLAIMED: "◆",
  EARLY_TERMINATED: "✗",
  RETURNED: "↩",
  OVERRULED: "✗",
  CLOSED: "✓",
  APPEAL_SUBMITTED: "◆",
  APPEAL_APPROVED: "✓",
  APPEAL_REJECTED: "✗",
};

export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? {
    display: status,
    color: "#43566c",
    bg: "#e8ecf1",
    description: "未知状态",
  };
  const icon = STATUS_ICON[status] ?? status;

  return (
    <span
      className="status-badge"
      data-status={status}
      role="status"
      aria-label={`${meta.display}，${meta.description}`}
      style={{ color: meta.color, background: meta.bg }}
    >
      <span aria-hidden="true" className="status-badge-icon">{icon}</span>
      <span className="status-badge-text">{meta.display}</span>
      <span className="visually-hidden">{meta.description}</span>
    </span>
  );
}
