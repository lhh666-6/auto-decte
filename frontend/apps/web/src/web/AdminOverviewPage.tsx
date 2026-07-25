import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

/* ── Types ───────────────────────────────────────────────────── */

interface OverviewStats {
  sort_today: number;
  sort_pending_supervisor: number;
  sort_pending_inspection: number;
  sort_pending_plant: number;
  sort_anomalies: number;
  dip_today: number;
  dip_pending_supervisor: number;
  dip_pending_inspection: number;
  dip_pending_plant: number;
  dip_anomalies: number;
}

/* ── Helpers ─────────────────────────────────────────────────── */

function StatBadge({ label, value, loading }: {
  label: string; value: number | string; loading: boolean;
}) {
  return (
    <div className="bp-stat-badge">
      <span className="bp-stat-num">{loading ? "—" : value}</span>
      <span className="bp-stat-lbl">{label}</span>
    </div>
  );
}

function StageFlow({ stages }: { stages: Array<{ label: string; sub?: string }> }) {
  return (
    <div className="bp-stage-flow">
      {stages.map((s, i) => (
        <span key={s.label}>
          <span className="bp-stage-node">{s.label}</span>
          {s.sub && <small className="bp-stage-sub">{s.sub}</small>}
          {i < stages.length - 1 && <span className="bp-stage-arrow">→</span>}
        </span>
      ))}
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────── */

export function AdminOverviewPage() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<OverviewStats>({
    sort_today: 0, sort_pending_supervisor: 0, sort_pending_inspection: 0,
    sort_pending_plant: 0, sort_anomalies: 0,
    dip_today: 0, dip_pending_supervisor: 0, dip_pending_inspection: 0,
    dip_pending_plant: 0, dip_anomalies: 0,
  });

  useEffect(() => {
    setLoading(true);
    fetch("/api/v1/admin/overview", { credentials: "include" })
      .then((r) => r.json())
      .then((data: Record<string, unknown>) => {
        const raw = data.stats as Record<string, number> | undefined;
        if (raw) setStats({
          sort_today: raw.sort_today ?? 0, sort_pending_supervisor: raw.sort_pending_supervisor ?? 0,
          sort_pending_inspection: raw.sort_pending_inspection ?? 0,
          sort_pending_plant: raw.sort_pending_plant ?? 0, sort_anomalies: raw.sort_anomalies ?? 0,
          dip_today: raw.dip_today ?? 0, dip_pending_supervisor: raw.dip_pending_supervisor ?? 0,
          dip_pending_inspection: raw.dip_pending_inspection ?? 0,
          dip_pending_plant: raw.dip_pending_plant ?? 0, dip_anomalies: raw.dip_anomalies ?? 0,
        });
      })
      .catch(() => { /* use empty state */ })
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="admin-overview-page">
      <h1 className="admin-page-title">业务全景</h1>
      <p className="admin-page-subtitle">两张正式业务表 · 独立记录 · 数据引用</p>

      {/* ═══ Business Form A: 《竹丝装笼跟踪牌》 ═══ */}
      <div className="bp-card bp-card-sort">
        <header className="bp-card-header">
          <h2>《竹丝装笼跟踪牌》</h2>
          <span className="bp-card-badge">已发布 · V1</span>
        </header>
        <p className="bp-card-desc">独立分选记录 · 主要岗位：分选工</p>

        <div className="bp-stats-row">
          <StatBadge label="今日记录" value={stats.sort_today} loading={loading} />
          <StatBadge label="待主管" value={stats.sort_pending_supervisor} loading={loading} />
          <StatBadge label="待检测" value={stats.sort_pending_inspection} loading={loading} />
          <StatBadge label="待厂长" value={stats.sort_pending_plant} loading={loading} />
          <StatBadge label="异常" value={stats.sort_anomalies} loading={loading} />
        </div>

        <StageFlow stages={[
          { label: "分选" },
          { label: "质量检测", sub: "检测员" },
          { label: "主管审核", sub: "主管" },
          { label: "厂长确认", sub: "厂长" },
        ]} />
      </div>

      {/* Data dependency arrow */}
      <div className="bp-dependency-arrow">
        <span>生产数据引用</span>
        <span className="bp-dep-icon">↓</span>
      </div>

      {/* ═══ Business Form B: 《配片数计量考核表》 ═══ */}
      <div className="bp-card bp-card-dip">
        <header className="bp-card-header">
          <h2>《配片数计量考核表》</h2>
          <span className="bp-card-badge">已发布 · V1</span>
        </header>
        <p className="bp-card-desc">浸胶 → 干燥 · 主要岗位：浸胶工、干燥工</p>

        <div className="bp-stats-row">
          <StatBadge label="今日记录" value={stats.dip_today} loading={loading} />
          <StatBadge label="待主管" value={stats.dip_pending_supervisor} loading={loading} />
          <StatBadge label="待检测" value={stats.dip_pending_inspection} loading={loading} />
          <StatBadge label="待厂长" value={stats.dip_pending_plant} loading={loading} />
          <StatBadge label="异常" value={stats.dip_anomalies} loading={loading} />
        </div>

        <StageFlow stages={[
          { label: "浸胶" },
          { label: "干燥" },
          { label: "质量检测", sub: "检测员" },
          { label: "主管审核", sub: "主管" },
          { label: "厂长确认", sub: "厂长" },
        ]} />
      </div>

      {/* Downstream summary */}
      <div className="bp-downstream">
        <div className="bp-down-box">
          <strong>正式生产事实</strong>
          <span>↓</span>
        </div>
        <div className="bp-down-box">
          <strong>岗位工资计算</strong>
          <span>↓</span>
        </div>
        <div className="bp-down-box">
          <strong>财务核算</strong>
          <span>↓</span>
        </div>
        <div className="bp-down-box">
          <strong>按岗位导出 XLSX</strong>
        </div>
      </div>

      {/* Quick links */}
      <div className="admin-quick-section">
        <h2>快速入口</h2>
        <div className="admin-quick-grid">
          <Link to="/admin/organization" className="admin-quick-card">
            <span className="admin-quick-icon">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 2a4 4 0 100 8 4 4 0 000-8zM3 18s-1 0-1-1 3-5 8-5 8 4 8 5-1 1-1 1H3z" stroke="currentColor" strokeWidth="1.5"/></svg>
            </span>
            <strong>组织与员工</strong>
            <small>管理员工档案、岗位分配、人员调动</small>
          </Link>
          <Link to="/admin/factories" className="admin-quick-card">
            <span className="admin-quick-icon">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M3 8V17h5V12h4v5h5V8L10 3 3 8z" stroke="currentColor" strokeWidth="1.5"/></svg>
            </span>
            <strong>工厂与岗位</strong>
            <small>查看工厂列表与岗位预设</small>
          </Link>
          <Link to="/admin/audit" className="admin-quick-card">
            <span className="admin-quick-icon">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M7 8h6M7 12h4" stroke="currentColor" strokeWidth="1.5"/></svg>
            </span>
            <strong>审计记录</strong>
            <small>查看操作审计日志</small>
          </Link>
        </div>
      </div>
    </section>
  );
}
