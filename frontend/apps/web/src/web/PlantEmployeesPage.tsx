import { useEffect, useState } from "react";

import {
  createPlantPersonnelTransfer,
  decidePlantPersonnelTransfer,
  listPlantEmployees,
  listPlantPersonnelTransfers,
  listPlantRoleOptions,
} from "./api";
import type { BambooEmployee, BambooPersonnelTransfer } from "./types";
import "./ledger-pages.css";

export function PlantEmployeesPage() {
  const [employees, setEmployees] = useState<BambooEmployee[]>([]);
  const [transfers, setTransfers] = useState<BambooPersonnelTransfer[]>([]);
  const [roles, setRoles] = useState<Array<{ role_code: string; display_name: string }>>([]);
  const [employeeCode, setEmployeeCode] = useState("");
  const [toRole, setToRole] = useState("");
  const [targetFactory, setTargetFactory] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  function reload() {
    void Promise.all([
      listPlantEmployees(),
      listPlantPersonnelTransfers(),
      listPlantRoleOptions(),
    ]).then(([people, movement, options]) => {
      setEmployees(people.items);
      setTransfers(movement.items);
      setRoles(options.items);
    }).catch((cause: unknown) => setError(
      cause instanceof Error ? cause.message : "人员数据加载失败",
    ));
  }
  useEffect(reload, []);

  async function submit() {
    try {
      await createPlantPersonnelTransfer({
        employee_code: employeeCode,
        to_role: toRole,
        target_factory_id: targetFactory,
        reason,
      });
      setReason("");
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "调动申请提交失败");
    }
  }

  return (
    <section className="ledger-page">
      <header><h1>本厂员工调动</h1><p>厂长发起本厂调岗或跨厂调动；跨厂须两厂厂长同意后交管理员执行。</p></header>
      {error && <div role="alert">{error}</div>}
      <div className="ledger-return-panel">
        <h2>发起调动</h2>
        <label>员工
          <select value={employeeCode} onChange={(event) => setEmployeeCode(event.target.value)}>
            <option value="">请选择</option>
            {employees.map((item) => (
              <option key={item.employee_code} value={item.employee_code}>
                {item.employee_name}（{item.role_name}）
              </option>
            ))}
          </select>
        </label>
        <label>目标职位
          <select value={toRole} onChange={(event) => setToRole(event.target.value)}>
            <option value="">请选择</option>
            {roles.map((item) => (
              <option key={item.role_code} value={item.role_code}>{item.display_name}</option>
            ))}
          </select>
        </label>
        <label>目标工厂
          <input value={targetFactory} onChange={(event) => setTargetFactory(event.target.value)} />
        </label>
        <label>调动原因
          <textarea value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
        <button
          type="button"
          disabled={!employeeCode || !toRole || !targetFactory || !reason.trim()}
          onClick={() => void submit()}
        >提交管理员流程</button>
      </div>
      <h2>调动记录</h2>
      <div className="ledger-case-list">
        {transfers.map((item) => (
          <article key={item.transfer_id}>
            <strong>{item.employee_code} · {item.from_role} → {item.to_role}</strong>
            <span>{item.source_factory_id} → {item.target_factory_id} · {item.status}</span>
            {item.status === "TARGET_MANAGER_PENDING" && item.target_factory_id && (
              <>
                <button type="button" onClick={() => void decidePlantPersonnelTransfer(
                  item.transfer_id, true, "目标厂长同意",
                ).then(reload)}>同意</button>
                <button type="button" onClick={() => void decidePlantPersonnelTransfer(
                  item.transfer_id, false, "目标厂长拒绝",
                ).then(reload)}>拒绝</button>
              </>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
