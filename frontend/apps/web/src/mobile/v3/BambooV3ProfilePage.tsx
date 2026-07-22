import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { MobileApiError, mobileApiClient, type BambooRoleChange } from "@form-detection/api-client";

import { useMobileSession } from "../session/MobileSessionProvider";
import { getPendingLogoutCount } from "../storage/session-cleanup";

const ROLE_LABELS: Record<string, string> = {
  SORT_OPERATOR: "分选工", DIPPING_OPERATOR: "浸胶工", DRYING_RACK_OPERATOR: "干燥工",
  INSPECTOR: "检测人", SUPERVISOR: "主管", PLANT_MANAGER: "厂长", FINANCE_APPROVER: "财务审批",
};

export function BambooV3ProfilePage() {
  const navigate = useNavigate();
  const { sessionMetadata: profile, logout } = useMobileSession();
  const [sheet, setSheet] = useState<"role" | "people" | null>(null);
  const [targetRole, setTargetRole] = useState("");
  const [reason, setReason] = useState("");
  const [employeeCode, setEmployeeCode] = useState("");
  const [assignmentRole, setAssignmentRole] = useState("");
  const [roleChanges, setRoleChanges] = useState<BambooRoleChange[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const role = profile?.bamboo_role ?? "";
  const network = navigator.onLine ? "联网" : "离线";

  useEffect(() => {
    if (role !== "PLANT_MANAGER") return;
    void mobileApiClient.listBambooRoleChanges().then(setRoleChanges).catch(() => setMessage("无法加载待处理的换岗申请"));
  }, [role]);

  if (!profile) return null;

  const run = async (operation: () => Promise<unknown>, success: string) => {
    setBusy(true); setMessage("");
    try { await operation(); setMessage(success); setSheet(null); }
    catch (cause) { setMessage(cause instanceof MobileApiError ? cause.problem.detail : "操作失败，请重试"); }
    finally { setBusy(false); }
  };

  const handleLogout = async () => {
    const pending = await getPendingLogoutCount();
    if (pending > 0 && !window.confirm(`本机还有 ${pending} 条未同步记录，确认退出吗？`)) return;
    await run(async () => { await logout(); navigate("/mobile/login", { replace: true }); }, "");
  };

  return (
    <div className="mobile-page bamboo-v3-page bamboo-v3-profile">
      <header className="bamboo-v3-page-header"><p>账号、班组与应用状态</p><h2>我的</h2></header>
      <section className="bamboo-v3-profile-card">
        <div className="bamboo-v3-avatar" aria-hidden="true">{profile.employee_name.charAt(0)}</div>
        <div><strong>{profile.employee_name}</strong><span>{profile.employee_code} · {profile.team_name}</span></div>
      </section>
      {message && <div className="mobile-status-banner" role="status">{message}</div>}
      <dl className="bamboo-v3-settings-card">
        <div><dt>所属工厂</dt><dd>{profile.factory_name || "待分配"}</dd></div>
        <div><dt>当前职务</dt><dd>{ROLE_LABELS[role] || profile.position || "待分配"}</dd></div>
        <div><dt>网络状态</dt><dd>{network}</dd></div>
        <div><dt>应用版本</dt><dd>V3</dd></div>
      </dl>
      <section className="bamboo-v3-profile-actions">
        {["SORT_OPERATOR", "DIPPING_OPERATOR", "DRYING_RACK_OPERATOR"].includes(role) && <button type="button" onClick={() => setSheet("role")}>申请换岗</button>}
        {role === "PLANT_MANAGER" && <button type="button" onClick={() => setSheet("people")}>人员与职务配置</button>}
        {role === "FINANCE_APPROVER" && <a href="/">财务工作请前往网页端</a>}
        <button type="button" className="danger" disabled={busy} onClick={() => void handleLogout()}>退出登录</button>
      </section>

      {sheet && <div className="bamboo-v3-sheet-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSheet(null); }}>
        <section className="bamboo-v3-bottom-sheet" role="dialog" aria-modal="true" aria-label={sheet === "role" ? "换岗申请" : "人员与职务配置"}>
          <div className="bamboo-v3-sheet-handle" />
          <header><h3>{sheet === "role" ? "换岗申请" : "人员与职务配置"}</h3><button type="button" aria-label="关闭" onClick={() => setSheet(null)}>×</button></header>
          {sheet === "role" ? <>
            <label>申请职务<input list="bamboo-role-options" value={targetRole} onChange={(event) => setTargetRole(event.target.value)} placeholder="输入或选择职务代码" /></label>
            <datalist id="bamboo-role-options"><option value="SORT_OPERATOR" /><option value="DIPPING_OPERATOR" /><option value="DRYING_RACK_OPERATOR" /></datalist>
            <label>申请原因<textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label>
            <button type="button" className="bamboo-sign-button" disabled={busy || !targetRole || !reason} onClick={() => void run(() => mobileApiClient.requestBambooRoleChange(targetRole, reason), "申请已提交，等待厂长同意")}>提交申请</button>
          </> : <>
            {roleChanges.filter((item) => item.status === "PENDING").length > 0 && <section className="bamboo-v3-role-requests"><h4>待处理换岗申请</h4>{roleChanges.filter((item) => item.status === "PENDING").map((item) => <article key={item.request_id}><strong>{item.employee_code}</strong><span>{ROLE_LABELS[item.from_role] || item.from_role} → {ROLE_LABELS[item.to_role] || item.to_role}</span><p>{item.reason}</p><div><button type="button" disabled={busy} onClick={() => void run(() => mobileApiClient.decideBambooRoleChange(item.request_id, true, "厂长同意"), "职务切换已通过")}>同意</button><button type="button" disabled={busy} onClick={() => void run(() => mobileApiClient.decideBambooRoleChange(item.request_id, false, "厂长驳回"), "申请已驳回")}>驳回</button></div></article>)}</section>}
            <p>可输入新增员工和未来职务代码，不限于当前选项。</p>
            <label>员工工号<input value={employeeCode} onChange={(event) => setEmployeeCode(event.target.value)} /></label>
            <label>职务代码<input list="manager-role-options" value={assignmentRole} onChange={(event) => setAssignmentRole(event.target.value)} /></label>
            <datalist id="manager-role-options"><option value="SUPERVISOR" /><option value="INSPECTOR" /><option value="SORT_OPERATOR" /><option value="DIPPING_OPERATOR" /><option value="DRYING_RACK_OPERATOR" /></datalist>
            <button type="button" className="bamboo-sign-button" disabled={busy || !employeeCode || !assignmentRole} onClick={() => void run(() => mobileApiClient.assignBambooEmployeeRole(employeeCode, assignmentRole), "职务已分配")}>分配职务</button>
          </>}
        </section>
      </div>}
    </div>
  );
}
