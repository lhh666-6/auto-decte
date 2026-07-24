import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

function StatCard({ label, value, loading }: { label: string; value: string; loading: boolean }) {
  return (
    <div className="admin-stat-card">
      <span className="admin-stat-value">{loading ? "—" : value}</span>
      <span className="admin-stat-label">{label}</span>
    </div>
  );
}

interface FlowNode {
  title: string;
  actor: string;
  detail: string;
}

const FLOW: FlowNode[] = [
  { title: "员工登录", actor: "全员", detail: "工号 + PIN 登录移动端" },
  { title: "生产记录", actor: "分选/浸胶/干燥工", detail: "填写工序数据：笼号、品级、含水率等" },
  { title: "主管审核", actor: "主管", detail: "审核工序数据，可打回重填" },
  { title: "质量检测", actor: "检测员", detail: "含水率 1-100 整数、品级检测、合格/不合格" },
  { title: "厂长审核", actor: "厂长", detail: "最终签字确认，可提前终止检测" },
  { title: "工资数据", actor: "系统", detail: "正式生产事实 → 工资计算" },
  { title: "岗位报表", actor: "财务", detail: "按岗位/工厂/日期筛选查看" },
  { title: "XLSX 导出", actor: "财务", detail: "固定格式一键导出" },
];

export function AdminOverviewPage() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<Record<string, number>>({});

  useEffect(() => {
    setLoading(true);
    fetch("/api/v1/admin/overview", { credentials: "include" })
      .then((r) => r.json())
      .then((data: Record<string, unknown>) => {
        const s: Record<string, number> = {};
        for (const card of (data.cards as Array<{ key: string; value: number }>) ?? []) {
          s[card.key] = card.value;
        }
        setStats(s);
      })
      .catch(() => { /* use empty state */ })
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="admin-overview-page">
      <h1 className="admin-page-title">业务全景</h1>
      <p className="admin-page-subtitle">竹丝工序生产管理 V1 主链路</p>

      {/* A: Stat cards */}
      <div className="admin-stat-grid">
        <StatCard label="待审批表单" value={String(stats.form_approvals ?? "—")} loading={loading} />
        <StatCard label="待审批流程" value={String(stats.workflow_approvals ?? "—")} loading={loading} />
        <StatCard label="待审批工资规则" value={String(stats.payroll_approvals ?? "—")} loading={loading} />
      </div>

      {/* B: V1 Business Flow */}
      <div className="admin-flow-section">
        <h2>V1 业务主链</h2>
        <div className="v1-flow">
          {FLOW.map((node, i) => (
            <div key={node.title} className="v1-flow-item">
              <div className="v1-flow-node">
                <strong>{node.title}</strong>
                <small>{node.actor}</small>
                <span>{node.detail}</span>
              </div>
              {i < FLOW.length - 1 && <div className="v1-flow-arrow">↓</div>}
            </div>
          ))}
        </div>
      </div>

      {/* C: Quick Entry */}
      <div className="admin-quick-section">
        <h2>快速入口</h2>
        <div className="admin-quick-grid">
          <Link to="/admin/organization" className="admin-quick-card">
            <span className="admin-quick-icon">👥</span>
            <strong>组织与员工</strong>
            <small>管理员工档案、岗位分配、人员调动</small>
          </Link>
          <Link to="/admin/factories" className="admin-quick-card">
            <span className="admin-quick-icon">🏭</span>
            <strong>工厂与岗位</strong>
            <small>查看工厂列表与岗位预设</small>
          </Link>
          <Link to="/admin/audit" className="admin-quick-card">
            <span className="admin-quick-icon">📋</span>
            <strong>审计记录</strong>
            <small>查看操作审计日志</small>
          </Link>
        </div>
      </div>
    </section>
  );
}
