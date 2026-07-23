import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  MobileApiError,
  mobileApiClient,
  type BambooFactory,
  type BambooFactoryEmployee,
  type BambooPersonnelTransfer,
  type BambooRoleOption,
} from "@form-detection/api-client";

import { useMobileSession } from "../session/MobileSessionProvider";

export function BambooPersonnelPage() {
  const { sessionMetadata: session } = useMobileSession();
  const [people, setPeople] = useState<BambooFactoryEmployee[]>([]);
  const [factories, setFactories] = useState<BambooFactory[]>([]);
  const [roles, setRoles] = useState<BambooRoleOption[]>([]);
  const [transfers, setTransfers] = useState<BambooPersonnelTransfer[]>([]);
  const [employeeCode, setEmployeeCode] = useState("");
  const [targetFactory, setTargetFactory] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [reason, setReason] = useState("");
  const [newEmployeeName, setNewEmployeeName] = useState("");
  const [newEmployeePin, setNewEmployeePin] = useState("");
  const [newEmployeeRole, setNewEmployeeRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const role = session?.bamboo_role ?? "";
  const admin = role === "SYSTEM_ADMIN";

  const load = useCallback(async () => {
    if (!["PLANT_MANAGER", "SYSTEM_ADMIN"].includes(role)) return;
    const [loadedPeople, loadedFactories, loadedRoles, loadedTransfers] = await Promise.all([
      mobileApiClient.listBambooFactoryEmployees(),
      mobileApiClient.listBambooFactories(),
      mobileApiClient.listBambooRoleOptions(),
      mobileApiClient.listBambooPersonnelTransfers(),
    ]);
    setPeople(loadedPeople);
    setFactories(loadedFactories);
    setRoles(loadedRoles);
    setTransfers(loadedTransfers);
    setTargetFactory((current) => current || session?.factory_id || loadedFactories[0]?.factory_id || "");
  }, [role, session?.factory_id]);

  useEffect(() => { void load().catch(() => setMessage("无法加载人员调度数据")); }, [load]);

  const selected = people.find((item) => item.employee_code === employeeCode);
  const selectableRoles = useMemo(
    () => roles.filter((item) => admin ? item.role_code === "PLANT_MANAGER" : !["PLANT_MANAGER", "FINANCE_APPROVER", "SYSTEM_ADMIN"].includes(item.role_code)),
    [admin, roles],
  );

  if (!session || !["PLANT_MANAGER", "SYSTEM_ADMIN"].includes(role)) {
    return <div className="mobile-page bamboo-v3-page"><h2>人员调度中心</h2><p>当前账号没有人员调度权限。</p></div>;
  }

  const run = async (operation: () => Promise<unknown>, success: string, afterSuccess?: () => void) => {
    setBusy(true);
    setMessage("");
    try {
      await operation();
      afterSuccess?.();
      setMessage(success);
      await load();
    } catch (cause) {
      setMessage(cause instanceof MobileApiError ? cause.problem.detail : "操作失败，请重试");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mobile-page bamboo-v3-page bamboo-personnel-page">
      <header className="bamboo-v3-page-header bamboo-v3-detail-heading">
        <Link to="/mobile/profile" aria-label="返回我的">‹</Link>
        <div><p>手机与电脑均可使用</p><h2>人员调度中心</h2></div>
      </header>
      {message && <div className="mobile-status-banner" role="status">{message}</div>}
      <div className="bamboo-personnel-layout">
        <section className="bamboo-sheet-section bamboo-personnel-form">
          <h3>{admin ? "更换厂长" : "发起人员调动"}</h3>
          <label>员工<select value={employeeCode} onChange={(event) => setEmployeeCode(event.target.value)}><option value="">请选择员工</option>{people.map((person) => <option key={person.employee_code} value={person.employee_code}>{person.employee_name}（{person.employee_code}）· {person.role_name}</option>)}</select></label>
          {selected && <p>当前工厂：{factories.find((item) => item.factory_id === selected.factory_id)?.name ?? selected.factory_id}</p>}
          <label>目标工厂<select value={targetFactory} onChange={(event) => setTargetFactory(event.target.value)}>{factories.map((factory) => <option key={factory.factory_id} value={factory.factory_id}>{factory.name}</option>)}</select></label>
          <label>目标职位<select value={targetRole} onChange={(event) => setTargetRole(event.target.value)}><option value="">请选择职位</option>{selectableRoles.map((item) => <option key={item.role_code} value={item.role_code}>{item.display_name}</option>)}</select></label>
          <label>调动说明<textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <button className="bamboo-sign-button" disabled={busy || !employeeCode || !targetFactory || !targetRole || !reason.trim()} onClick={() => void run(
            () => mobileApiClient.createBambooPersonnelTransfer({ employee_code: employeeCode, to_role: targetRole, target_factory_id: targetFactory, reason: reason.trim() }),
            admin ? "厂长更换已提交，等待管理员执行" : "调动已提交",
          )}>{admin ? "建立厂长更换单" : "提交人员调动"}</button>
        </section>

        <section className="bamboo-sheet-section bamboo-personnel-queue">
          <h3>调动审批与执行</h3>
          {transfers.length === 0 ? <p>暂无人员调动记录</p> : transfers.map((item) => (
            <article key={item.transfer_id}>
              <strong>{people.find((person) => person.employee_code === item.employee_code)?.employee_name ?? item.employee_code}</strong>
              <span>{item.source_factory_id} → {item.target_factory_id} · {item.from_role} → {item.to_role}</span>
              <p>{item.reason}</p><em>{transferStatus(item.status)}</em>
              {role === "PLANT_MANAGER" && item.status === "TARGET_MANAGER_PENDING" && item.target_factory_id === session.factory_id && <div className="btnrow"><button disabled={busy} onClick={() => void run(() => mobileApiClient.decideBambooPersonnelTransferAsManager(item.transfer_id, false, "目标厂长驳回"), "已驳回")}>驳回</button><button disabled={busy} onClick={() => void run(() => mobileApiClient.decideBambooPersonnelTransferAsManager(item.transfer_id, true, "目标厂长同意"), "已同意并提交管理员")}>同意</button></div>}
              {admin && item.status === "ADMIN_PENDING" && <div className="btnrow"><button disabled={busy} onClick={() => void run(() => mobileApiClient.executeBambooPersonnelTransfer(item.transfer_id, false, "管理员驳回"), "已驳回")}>驳回</button><button disabled={busy} onClick={() => void run(() => mobileApiClient.executeBambooPersonnelTransfer(item.transfer_id, true, "管理员执行"), "调动已完成并通知员工")}>执行调动</button></div>}
            </article>
          ))}
        </section>

        {!admin && <section className="bamboo-sheet-section bamboo-personnel-form">
          <h3>添加本厂新员工</h3>
          <label>员工姓名<input value={newEmployeeName} onChange={(event) => setNewEmployeeName(event.target.value)} /></label>
          <label>初始登录 PIN<input type="password" inputMode="numeric" value={newEmployeePin} onChange={(event) => setNewEmployeePin(event.target.value.replace(/\D/g, ""))} placeholder="4—12 位数字" /></label>
          <label>初始职位<select value={newEmployeeRole} onChange={(event) => setNewEmployeeRole(event.target.value)}><option value="">请选择职位</option>{selectableRoles.map((item) => <option key={item.role_code} value={item.role_code}>{item.display_name}</option>)}</select></label>
          <button className="bamboo-sign-button" disabled={busy || !newEmployeeName.trim() || !/^\d{4,12}$/.test(newEmployeePin) || !newEmployeeRole} onClick={() => void run(
            () => mobileApiClient.createBambooFactoryEmployee(newEmployeeName.trim(), newEmployeePin, newEmployeeRole),
            "新员工已添加到本厂",
            () => { setNewEmployeeName(""); setNewEmployeePin(""); setNewEmployeeRole(""); },
          )}>添加到本厂</button>
        </section>}
      </div>
    </div>
  );
}

function transferStatus(status: string): string {
  return ({ TARGET_MANAGER_PENDING: "等待目标厂长同意", ADMIN_PENDING: "等待管理员执行", EXECUTED: "调动完成", REJECTED: "已驳回" } as Record<string, string>)[status] ?? status;
}
