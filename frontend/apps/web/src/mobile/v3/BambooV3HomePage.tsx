import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { MobileApiError, mobileApiClient, type BambooDashboard } from "@form-detection/api-client";

import { useMobileSession } from "../session/MobileSessionProvider";

const EMPTY_DASHBOARD: BambooDashboard = { available: 0, waiting: 0, completed: 0 };

const ROLE_LABELS: Record<string, string> = {
  SORT_OPERATOR: "分选工",
  DIPPING_OPERATOR: "浸胶工",
  DRYING_RACK_OPERATOR: "干燥工",
  INSPECTOR: "检测人",
  SUPERVISOR: "主管",
  PLANT_MANAGER: "厂长",
  FINANCE_APPROVER: "财务审批",
};

const ROLE_ACTIONS: Record<string, { title: string; description: string }> = {
  SORT_OPERATOR: { title: "开始记录工作", description: "建立记录并完成分选工序" },
  DIPPING_OPERATOR: { title: "开始记录工作", description: "处理已开放的浸胶工序" },
  DRYING_RACK_OPERATOR: { title: "开始记录工作", description: "处理已开放的干燥工序" },
  INSPECTOR: { title: "开始记录工作", description: "检测数据与现场留痕" },
  SUPERVISOR: { title: "开始记录工作", description: "查看整张表单并完成主管审核" },
  PLANT_MANAGER: { title: "开始记录工作", description: "查看整张表单并完成厂长签字" },
};

export function BambooV3HomePage() {
  const { sessionMetadata: session } = useMobileSession();
  const [dashboard, setDashboard] = useState<BambooDashboard>(EMPTY_DASHBOARD);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [online, setOnline] = useState(() => typeof navigator === "undefined" || navigator.onLine);

  const role = session?.bamboo_role ?? "";
  const isFinance = role === "FINANCE_APPROVER";
  const hasMobileWork = Boolean(ROLE_ACTIONS[role]);

  const loadDashboard = useCallback(async () => {
    if (!hasMobileWork) return;
    setLoading(true);
    setError("");
    try {
      setDashboard(await mobileApiClient.getBambooDashboard());
    } catch (cause) {
      setError(cause instanceof MobileApiError
        ? cause.problem.detail
        : "暂时无法加载工作统计，请检查网络后重试");
    } finally {
      setLoading(false);
    }
  }, [hasMobileWork]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  const roleLabel = ROLE_LABELS[role] || session?.position || "待分配";
  const action = ROLE_ACTIONS[role];

  return (
    <div className="mobile-page bamboo-v3-home">
      <header className="bamboo-v3-hero">
        <span className="bamboo-v3-eyebrow">BAMBOO WORKFLOW</span>
        <h1>竹丝工序记录</h1>
        <p>完成工作后主动记录</p>
      </header>

      <section className="bamboo-v3-identity" aria-label="当前账号">
        <div className="bamboo-v3-person">
          <span className="bamboo-v3-avatar" aria-hidden="true">{(session?.employee_name || "人").slice(0, 1)}</span>
          <div><strong>{session?.employee_name || "当前人员"}</strong><span>{session?.employee_code || "—"}</span></div>
          <span className={`bamboo-network-pill ${online ? "is-online" : "is-offline"}`}>
            <i aria-hidden="true" />{online ? "联网" : "离线"}
          </span>
        </div>
        <dl>
          <div><dt>工厂</dt><dd>{session?.factory_name || "待分配"}</dd></div>
          <div><dt>职务</dt><dd>{roleLabel}</dd></div>
        </dl>
      </section>

      {hasMobileWork && (
        <section className="bamboo-v3-dashboard" aria-label="工作统计" aria-busy={loading}>
          <div><span>可处理</span><strong>{loading ? "—" : dashboard.available}</strong></div>
          <div><span>等待中</span><strong>{loading ? "—" : dashboard.waiting}</strong></div>
          <div><span>已完成</span><strong>{loading ? "—" : dashboard.completed}</strong></div>
        </section>
      )}

      {error && (
        <div className="error-banner bamboo-v3-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void loadDashboard()}>重试</button>
        </div>
      )}

      <section className="bamboo-v3-work-entry" aria-label="工作入口">
        {action && (
          <Link className="bamboo-v3-action-card" to="/mobile/work">
            <span><strong>{action.title}</strong><small>{action.description}</small></span>
            <b aria-hidden="true">›</b>
          </Link>
        )}

        {!role && (
          <div className="bamboo-v3-notice" role="status">
            <strong>等待管理员或厂长分配职务</strong>
            <span>职务分配完成后，这里会显示对应的工作入口。</span>
          </div>
        )}

        {isFinance && (
          <div className="bamboo-v3-notice bamboo-v3-finance-notice">
            <strong>财务审批请前往网页端</strong>
            <span>移动端不提供财务审批操作，请使用电脑访问系统。</span>
            <a href="/">进入网页端</a>
          </div>
        )}
      </section>
    </div>
  );
}
