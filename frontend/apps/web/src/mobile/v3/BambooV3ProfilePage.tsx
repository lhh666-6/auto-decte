import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  MobileApiError,
  mobileApiClient,
  type BambooFactoryEmployee,
  type BambooRoleChange,
  type BambooRoleOption,
} from "@form-detection/api-client";

import { useMobileSession } from "../session/MobileSessionProvider";
import { usePwaInstall } from "../pwa/usePwaInstall";
import { getPendingLogoutCount } from "../storage/session-cleanup";

const ROLE_LABELS: Record<string, string> = {
  SORT_OPERATOR: "分选工",
  DIPPING_OPERATOR: "浸胶工",
  DRYING_RACK_OPERATOR: "干燥工",
  INSPECTOR: "检测人",
  SUPERVISOR: "主管",
  PLANT_MANAGER: "厂长",
  FINANCE_APPROVER: "财务审批",
};

type Sheet = "role" | "requests" | "people" | "add-person" | null;

export function BambooV3ProfilePage() {
  const navigate = useNavigate();
  const { sessionMetadata: profile, logout } = useMobileSession();
  const pwa = usePwaInstall();
  const [sheet, setSheet] = useState<Sheet>(null);
  const [roleOptions, setRoleOptions] = useState<BambooRoleOption[]>([]);
  const [people, setPeople] = useState<BambooFactoryEmployee[]>([]);
  const [roleChanges, setRoleChanges] = useState<BambooRoleChange[]>([]);
  const [targetRole, setTargetRole] = useState("");
  const [reason, setReason] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState("");
  const [assignmentRole, setAssignmentRole] = useState("");
  const [newEmployeeName, setNewEmployeeName] = useState("");
  const [newEmployeePin, setNewEmployeePin] = useState("");
  const [newEmployeeRole, setNewEmployeeRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const role = profile?.bamboo_role ?? "";
  const network = navigator.onLine ? "联网" : "离线";
  const pendingRequests = roleChanges.filter((item) => item.status === "PENDING");
  const requestableRoles = roleOptions.filter(
    (item) => item.self_requestable && item.role_code !== role,
  );

  const reloadManagerData = useCallback(async () => {
    if (role !== "PLANT_MANAGER") return;
    const [requests, employees] = await Promise.all([
      mobileApiClient.listBambooRoleChanges(),
      mobileApiClient.listBambooFactoryEmployees(),
    ]);
    setRoleChanges(requests);
    setPeople(employees);
  }, [role]);

  useEffect(() => {
    void mobileApiClient.listBambooRoleOptions().then(setRoleOptions).catch(() => {
      setMessage("无法加载管理员发布的职位，请稍后重试");
    });
    void reloadManagerData().catch(() => {
      setMessage("无法加载本厂人员或换岗申请");
    });
  }, [reloadManagerData]);

  const roleName = useCallback(
    (code: string) => roleOptions.find((item) => item.role_code === code)?.display_name
      ?? ROLE_LABELS[code]
      ?? code,
    [roleOptions],
  );
  const employeeName = useCallback(
    (code: string) => people.find((item) => item.employee_code === code)?.employee_name ?? code,
    [people],
  );

  if (!profile) return null;

  const run = async (
    operation: () => Promise<unknown>,
    success: string,
    after?: () => void | Promise<void>,
  ) => {
    setBusy(true);
    setMessage("");
    try {
      await operation();
      await after?.();
      setMessage(success);
      setSheet(null);
    } catch (cause) {
      setMessage(cause instanceof MobileApiError ? cause.problem.detail : "操作失败，请重试");
    } finally {
      setBusy(false);
    }
  };

  const handleLogout = async () => {
    const pending = await getPendingLogoutCount();
    if (pending > 0 && !window.confirm(`本机还有 ${pending} 条未同步记录，确认退出吗？`)) return;
    await run(async () => {
      await logout();
      navigate("/mobile/login", { replace: true });
    }, "");
  };

  const currentPerson = people.find((item) => item.employee_code === selectedEmployee);

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
        <div><dt>当前职务</dt><dd>{roleName(role) || profile.position || "待分配"}</dd></div>
        <div><dt>网络状态</dt><dd>{network}</dd></div>
        <div><dt>应用版本</dt><dd>V3</dd></div>
      </dl>
      <section className="bamboo-v3-profile-actions">
        {requestableRoles.length > 0 && (
          <button type="button" onClick={() => setSheet("role")}>申请换岗</button>
        )}
        {role === "PLANT_MANAGER" && <>
          <button type="button" onClick={() => setSheet("requests")}>
            换岗审批{pendingRequests.length ? `（${pendingRequests.length}）` : ""}
          </button>
          <button type="button" onClick={() => setSheet("people")}>本厂人员与调动</button>
          <button type="button" onClick={() => setSheet("add-person")}>添加新人员</button>
        </>}
        {role === "FINANCE_APPROVER" && <a href="/">财务工作请前往网页端</a>}
        <button type="button" disabled={pwa.installed} onClick={() => void pwa.install().then((result) => {
          if (result === "unavailable") setMessage("请使用浏览器菜单中的“添加到主屏幕”或“安装应用”。微信内打开时，可先选择“在浏览器打开”。");
          else if (result === "dismissed") setMessage("已取消安装，稍后仍可再次添加到桌面。");
          else setMessage("已添加到桌面，可像普通应用一样打开。");
        })}>{pwa.installed ? "已安装到桌面" : pwa.canInstall ? "一键添加到桌面" : "添加到桌面"}</button>
        <button type="button" className="danger" disabled={busy} onClick={() => void handleLogout()}>退出登录</button>
      </section>

      {sheet && (
        <div className="bamboo-v3-sheet-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !busy) setSheet(null);
        }}>
          <section className="bamboo-v3-bottom-sheet" role="dialog" aria-modal="true" aria-label={sheetTitle(sheet)}>
            <div className="bamboo-v3-sheet-handle" />
            <header><h3>{sheetTitle(sheet)}</h3><button type="button" aria-label="关闭" onClick={() => setSheet(null)} disabled={busy}>×</button></header>

            {sheet === "role" && <>
              <label>申请职位
                <select value={targetRole} onChange={(event) => setTargetRole(event.target.value)}>
                  <option value="">请选择管理员发布的职位</option>
                  {requestableRoles.map((item) => <option key={item.role_code} value={item.role_code}>{item.display_name}</option>)}
                </select>
              </label>
              <label>申请原因<textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label>
              <button type="button" className="bamboo-sign-button" disabled={busy || !targetRole || !reason.trim()} onClick={() => void run(
                () => mobileApiClient.requestBambooRoleChange(targetRole, reason.trim()),
                "申请已提交，等待厂长处理",
                () => { setTargetRole(""); setReason(""); },
              )}>提交换岗申请</button>
            </>}

            {sheet === "requests" && (
              pendingRequests.length === 0
                ? <p className="bamboo-v3-empty-copy">当前没有待处理的换岗申请</p>
                : <section className="bamboo-v3-role-requests">{pendingRequests.map((item) => (
                  <article key={item.request_id}>
                    <strong>{employeeName(item.employee_code)}（{item.employee_code}）</strong>
                    <span>{roleName(item.from_role)} → {roleName(item.to_role)}</span>
                    <p>{item.reason}</p>
                    <div>
                      <button type="button" disabled={busy} onClick={() => void run(
                        () => mobileApiClient.decideBambooRoleChange(item.request_id, true, "厂长同意"),
                        "换岗申请已通过",
                        reloadManagerData,
                      )}>同意</button>
                      <button type="button" disabled={busy} onClick={() => void run(
                        () => mobileApiClient.decideBambooRoleChange(item.request_id, false, "厂长驳回"),
                        "换岗申请已驳回",
                        reloadManagerData,
                      )}>驳回</button>
                    </div>
                  </article>
                ))}</section>
            )}

            {sheet === "people" && <>
              <label>选择本厂员工
                <select value={selectedEmployee} onChange={(event) => {
                  setSelectedEmployee(event.target.value);
                  const selected = people.find((item) => item.employee_code === event.target.value);
                  setAssignmentRole(selected?.role_code ?? "");
                }}>
                  <option value="">请选择员工</option>
                  {people.map((item) => <option key={item.employee_code} value={item.employee_code}>{item.employee_name}（{item.employee_code}）· {item.role_name}</option>)}
                </select>
              </label>
              {currentPerson && <p>当前职位：{currentPerson.role_name}</p>}
              <label>调整为
                <select value={assignmentRole} onChange={(event) => setAssignmentRole(event.target.value)}>
                  <option value="">请选择预设职位</option>
                  {roleOptions.map((item) => <option key={item.role_code} value={item.role_code}>{item.display_name}</option>)}
                </select>
              </label>
              <button type="button" className="bamboo-sign-button" disabled={busy || !selectedEmployee || !assignmentRole || assignmentRole === currentPerson?.role_code} onClick={() => void run(
                () => mobileApiClient.assignBambooEmployeeRole(selectedEmployee, assignmentRole),
                "人员职位已调整",
                reloadManagerData,
              )}>确认人员调动</button>
            </>}

            {sheet === "add-person" && <>
              <label>员工姓名<input value={newEmployeeName} onChange={(event) => setNewEmployeeName(event.target.value)} placeholder="请输入真实姓名" /></label>
              <label>初始登录 PIN<input type="password" inputMode="numeric" value={newEmployeePin} onChange={(event) => setNewEmployeePin(event.target.value.replace(/\D/g, ""))} placeholder="4—12 位数字" /></label>
              <label>初始职位
                <select value={newEmployeeRole} onChange={(event) => setNewEmployeeRole(event.target.value)}>
                  <option value="">请选择预设职位</option>
                  {roleOptions.map((item) => <option key={item.role_code} value={item.role_code}>{item.display_name}</option>)}
                </select>
              </label>
              <p>职位由管理员预设；厂长只能从列表中选择，不能新增职位。</p>
              <button type="button" className="bamboo-sign-button" disabled={busy || !newEmployeeName.trim() || !/^\d{4,12}$/.test(newEmployeePin) || !newEmployeeRole} onClick={() => void run(
                () => mobileApiClient.createBambooFactoryEmployee(newEmployeeName.trim(), newEmployeePin, newEmployeeRole),
                "新人员已添加，可使用生成工号和初始 PIN 登录",
                async () => {
                  setNewEmployeeName(""); setNewEmployeePin(""); setNewEmployeeRole("");
                  await reloadManagerData();
                },
              )}>添加到本厂</button>
            </>}
          </section>
        </div>
      )}
    </div>
  );
}

function sheetTitle(sheet: Exclude<Sheet, null>): string {
  return ({
    role: "申请换岗",
    requests: "换岗审批",
    people: "本厂人员与调动",
    "add-person": "添加新人员",
  })[sheet];
}
