import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { MobileApiError, mobileApiClient, type BambooDashboard, type BambooInspectionWindow, type MobileSubmissionListItem } from "@form-detection/api-client";

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

const ROLE_ACTIONS: Record<string, { primaryTitle: string; primaryDesc: string; secondaryTitle: string; secondaryDesc: string }> = {
  SORT_OPERATOR: {
    primaryTitle: "记录分选/装笼工序",
    primaryDesc: "选择刚完成工序的在产竹丝笼",
    secondaryTitle: "查看我的分选/装笼记录",
    secondaryDesc: "查看本人提交与后续流转状态",
  },
  DIPPING_OPERATOR: {
    primaryTitle: "记录浸胶工序",
    primaryDesc: "只显示分选完成后流转到浸胶的竹丝记录",
    secondaryTitle: "查看我的浸胶记录",
    secondaryDesc: "查看本人提交与后续流转状态",
  },
  DRYING_RACK_OPERATOR: {
    primaryTitle: "记录干燥装架工序",
    primaryDesc: "浸胶和干燥在当前流程中联合作业签字",
    secondaryTitle: "查看我的干燥记录",
    secondaryDesc: "查看本人提交与后续流转状态",
  },
  INSPECTOR: {
    primaryTitle: "记录质量检测",
    primaryDesc: "查看当前可检测的生产记录并填写现场检测结果。",
    secondaryTitle: "查看我的检测记录",
    secondaryDesc: "查看检测序号、检测流程和现场留痕",
  },
  SUPERVISOR: {
    primaryTitle: "查看待把关记录",
    primaryDesc: "只显示当前流程已经到达本人环节的竹丝记录",
    secondaryTitle: "查看全部流程",
    secondaryDesc: "可打开整张电子表单并按需选择性回退",
  },
  PLANT_MANAGER: {
    primaryTitle: "查看待签字记录",
    primaryDesc: "上游主管完成后才会开放厂长确认",
    secondaryTitle: "人员与职务配置",
    secondaryDesc: "处理换岗申请，并为新人或未来岗位预留职务",
  },
};

export function BambooV3HomePage() {
  const { sessionMetadata: session } = useMobileSession();
  const [dashboard, setDashboard] = useState<BambooDashboard>(EMPTY_DASHBOARD);
  const [submissions, setSubmissions] = useState<MobileSubmissionListItem[]>([]);
  const [inspectionHistory, setInspectionHistory] = useState<BambooInspectionWindow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  const role = session?.bamboo_role ?? "";
  const isFinance = role === "FINANCE_APPROVER";
  const isInspector = role === "INSPECTOR";
  const isPlantManager = role === "PLANT_MANAGER";
  const action = ROLE_ACTIONS[role];
  const hasMobileWork = Boolean(action) && !isPlantManager;

  const loadDashboard = useCallback(async () => {
    if (!hasMobileWork) return;
    setLoading(true);
    setError("");
    try {
      if (isInspector) {
        const [summary, history] = await Promise.all([
          mobileApiClient.getBambooDashboard(),
          mobileApiClient.listBambooInspectionQueue("history"),
        ]);
        setDashboard(summary);
        setInspectionHistory(history.items.slice(0, 3));
      } else {
        const [summary, remoteSubmissions] = await Promise.all([
          mobileApiClient.getBambooDashboard(),
          typeof mobileApiClient.listSubmissions === "function"
            ? mobileApiClient.listSubmissions().catch(() => ({ submissions: [] }))
            : Promise.resolve({ submissions: [] }),
        ]);
        setDashboard(summary);
        setSubmissions(remoteSubmissions.submissions.slice(0, 3));
      }
      setLoaded(true);
    } catch (cause) {
      setError(cause instanceof MobileApiError
        ? cause.problem.detail
        : "暂时无法加载工作统计，请检查网络后重试");
    } finally {
      setLoading(false);
    }
  }, [hasMobileWork, isInspector]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const roleLabel = ROLE_LABELS[role] || session?.position || "待分配";

  return (
    <div className="page bamboo-v3-home">
      <h1 className="visually-hidden">竹丝工序记录</h1>
      <p className="visually-hidden">完成工作后主动记录</p>
      <span className="visually-hidden">联网</span>
      <span className="visually-hidden">{session?.employee_name || "当前人员"}</span>
      <span className="visually-hidden">{session?.factory_name || session?.team_name || "待分配工厂"}</span>
      <span className="visually-hidden">{roleLabel}</span>
      <section className="hero" aria-label="当前账号">
        <div className="hello">你好，{session?.employee_name || "当前人员"}</div>
        <div className="meta">{session?.employee_code || "—"} · {session?.factory_name || session?.team_name || "待分配工厂"} · {roleLabel}</div>
        {hasMobileWork && !error && (
          <div className="stats" aria-label="工作统计" aria-busy={loading}>
            <div className="stat"><span className="visually-hidden">可处理</span><b>{loading || !loaded ? "—" : dashboard.available}</b><span>当前可记录</span></div>
            <div className="stat"><span className="visually-hidden">等待中</span><b>{loading || !loaded ? "—" : dashboard.waiting}</b><span>等待上游</span></div>
            <div className="stat"><span className="visually-hidden">已完成</span><b>{loading || !loaded ? "—" : dashboard.completed}</b><span>今日提交</span></div>
          </div>
        )}
      </section>

      {error && (
        <div className="banner danger" role="alert">
          <span>{error}</span>
          <button type="button" className="btn small secondary" onClick={() => void loadDashboard()}>重试</button>
        </div>
      )}

      <section className="section" aria-label="记录工作">
        <div className="section-head">
          <div className="section-title">记录工作</div>
          <div className="section-note">完成后主动填写</div>
        </div>

        {action && !isPlantManager && (
          <div className="action-grid">
            <Link className="action-card" to="/mobile/work">
              <span className="visually-hidden">开始记录工作</span>
              <span className="icon" aria-hidden="true">✍</span>
              <span className="body">
                <span className="title">{action.primaryTitle}</span>
                <span className="desc">{action.primaryDesc}</span>
              </span>
              <span className="arrow" aria-hidden="true">›</span>
            </Link>
            <Link className="action-card" to={role === "PLANT_MANAGER" ? "/mobile/profile" : "/mobile/submissions"}>
              <span className="icon" aria-hidden="true">{role === "PLANT_MANAGER" ? "👥" : "✓"}</span>
              <span className="body">
                <span className="title">{action.secondaryTitle}</span>
                <span className="desc">{action.secondaryDesc}</span>
              </span>
              <span className="arrow" aria-hidden="true">›</span>
            </Link>
          </div>
        )}

        {!role && (
          <div className="card">
            <div className="card-body">
              <div className="card-title">等待管理员或厂长分配职务</div>
              <p className="empty-copy">职务分配完成后，这里会显示对应的工作入口。</p>
            </div>
          </div>
        )}

        {isFinance && (
          <div className="card">
            <div className="card-body">
              <div className="card-title">财务审批请前往网页端</div>
              <p className="empty-copy">移动端不提供财务审批操作，请使用电脑访问系统。</p>
              <a className="btn secondary full" href="/">进入网页端</a>
            </div>
          </div>
        )}

        {isPlantManager && (
          <div className="card">
            <div className="card-body">
              <div className="card-title">厂长业务请使用 Web 工作区</div>
              <p className="empty-copy">人员调度、审批把关等管理操作请在电脑端完成。</p>
              <a className="btn secondary full" href="/">进入网页端</a>
            </div>
          </div>
        )}
      </section>

      {hasMobileWork && (
        <section className="section" aria-label="最近提交">
          <div className="section-head">
            <div className="section-title">{isInspector ? "最近检测" : "最近提交"}</div>
            <div className="section-note">{isInspector ? inspectionHistory.length : submissions.length} 条</div>
          </div>
          {isInspector ? (
            inspectionHistory.length === 0 ? (
              <div className="card empty">
                <h3>暂无检测记录</h3>
                <p>完成一次质量检测后，会在这里看到最近的检测结果。</p>
              </div>
            ) : (
              <div className="list">
                {inspectionHistory.map((window) => (
                  <article className="record-card" key={window.record_id}>
                    <div className="record-top">
                      <div>
                        <div className="record-no">{window.display_no}</div>
                        <div className="record-meta">笼号 {window.cage_no || "—"} · {window.status === "COMPLETED" ? "检测完成" : inspectionStatusLabel(window.status)} · {window.completed_at ? formatTime(window.completed_at) : window.opened_at ? formatTime(window.opened_at) : ""}</div>
                      </div>
                      <span className={`chip ${window.status === "COMPLETED" ? "ok" : "wait"}`}>{window.status === "COMPLETED" ? "已完成" : "进行中"}</span>
                    </div>
                  </article>
                ))}
              </div>
            )
          ) : (
            submissions.length === 0 ? (
              <div className="card empty">
                <h3>暂无提交记录</h3>
                <p>完成一次工序签字后，会在这里看到最近流转状态。</p>
              </div>
            ) : (
              <div className="list">
                {submissions.map((item) => (
                  <article className="record-card" key={item.submission_id}>
                    <div className="record-top">
                      <div>
                        <div className="record-no">{item.form_id || item.submission_id}</div>
                        <div className="record-meta">提交单号 {item.submission_id} · {formatTime(item.submitted_at)}</div>
                      </div>
                      <span className="chip ok">{submissionStatus(item.status)}</span>
                    </div>
                  </article>
                ))}
              </div>
            )
          )}
        </section>
      )}
    </div>
  );
}

function submissionStatus(status: string): string {
  return ({ ACCEPTED: "已接收", COMPLETED: "已完成", APPROVED: "已通过", PENDING: "等待中" } as Record<string, string>)[status] ?? status;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function inspectionStatusLabel(status: string): string {
  return ({ OPEN: "待领取", CLAIMED: "检测中", COMPLETED: "检测完成", EARLY_TERMINATED: "提前终止", EXPIRED: "已超时", APPEAL_CLAIMED: "申诉中", APPEAL_SUBMITTED: "申诉待审批", APPEAL_APPROVED: "申诉已通过", APPEAL_REJECTED: "申诉已驳回" } as Record<string, string>)[status] ?? status;
}
