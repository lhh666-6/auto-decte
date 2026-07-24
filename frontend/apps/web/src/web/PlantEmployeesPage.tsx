import { useEffect, useState } from "react";

import {
  createPlantPersonnelTransfer,
  decidePlantPersonnelTransfer,
  listPlantEmployees,
  listPlantPersonnelTransfers,
  listPlantRoleOptions,
} from "./api";
import type { BambooEmployee, BambooPersonnelTransfer } from "./types";
import { useWebSession } from "./WebSessionProvider";
import "./ledger-pages.css";

const TRANSFER_STATUS_LABELS: Record<string, string> = {
  SOURCE_MANAGER_PENDING: "待源厂长审批",
  TARGET_MANAGER_PENDING: "待目标厂长审批",
  ADMIN_PENDING: "待管理员执行",
  APPROVED: "已批准",
  REJECTED: "已拒绝",
  EXECUTED: "已执行",
  CANCELLED: "已取消",
};

export function PlantEmployeesPage() {
  const { session } = useWebSession();
  const [employees, setEmployees] = useState<BambooEmployee[]>([]);
  const [transfers, setTransfers] = useState<BambooPersonnelTransfer[]>([]);
  const [roles, setRoles] = useState<Array<{ role_code: string; display_name: string }>>([]);
  const [factories, setFactories] = useState<Array<{ factory_id: string; factory_name: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // 调动表单
  const [showTransferForm, setShowTransferForm] = useState(false);
  const [employeeCode, setEmployeeCode] = useState("");
  const [toRole, setToRole] = useState("");
  const [targetFactory, setTargetFactory] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 调动决定备注（按 transfer_id 独立存储，避免跨调动串用）
  const [decisionNote, setDecisionNote] = useState<Record<string, string>>({});

  function getDecisionNote(transferId: string): string {
    return decisionNote[transferId] || "";
  }

  function setDecisionNoteFor(transferId: string, note: string) {
    setDecisionNote((prev) => ({ ...prev, [transferId]: note }));
  }

  function reload() {
    setLoading(true);
    void Promise.all([
      listPlantEmployees(),
      listPlantPersonnelTransfers(),
      listPlantRoleOptions(),
      fetch("/api/v1/plant/factories", { credentials: "include" }).then((r) => r.json()) as Promise<{ items: Array<{ factory_id: string; factory_name: string }> }>,
    ]).then(([people, movement, options, factoryResult]) => {
      setEmployees(people.items);
      setTransfers(movement.items);
      setRoles(options.items);
      setFactories(factoryResult.items || []);
      setLoading(false);
    }).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "人员数据加载失败");
      setLoading(false);
    });
  }
  useEffect(reload, []);

  // ---- 岗位分组标签 ----
  const ROLE_GROUP_LABELS: Record<string, string> = {
    SORT: "分选",
    DIP: "浸胶",
    DRY: "干燥",
    INSPECTION: "检测",
    SUPERVISOR: "主管",
  };

  function roleGroupLabel(roleCode: string): string {
    for (const [prefix, label] of Object.entries(ROLE_GROUP_LABELS)) {
      if (roleCode.toUpperCase().startsWith(prefix)) return label;
    }
    return roleCode;
  }

  // ---- 按岗位分组统计 ----
  const roleGroupCounts: Record<string, number> = {};
  for (const emp of employees) {
    const group = roleGroupLabel(emp.role_code);
    roleGroupCounts[group] = (roleGroupCounts[group] || 0) + 1;
  }

  // ---- 当前员工是否有待处理调动 ----
  function employeePendingTransfer(empCode: string): boolean {
    return transfers.some(
      (t) =>
        t.employee_code === empCode &&
        !["APPROVED", "EXECUTED", "REJECTED", "CANCELLED"].includes(t.status),
    );
  }

  // ---- 是否为本厂调动（目标工厂为空或等于当前员工的工厂） ----
  function isIntraPlant(
    employee: BambooEmployee,
    targetFactoryId: string,
  ): boolean {
    return !targetFactoryId || targetFactoryId === employee.factory_id;
  }

  async function submitTransfer() {
    if (!employeeCode || !toRole || !reason.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      await createPlantPersonnelTransfer({
        employee_code: employeeCode,
        to_role: toRole,
        target_factory_id: targetFactory || employees.find((e) => e.employee_code === employeeCode)?.factory_id || "",
        reason: reason.trim(),
      });
      setShowTransferForm(false);
      setEmployeeCode("");
      setToRole("");
      setTargetFactory("");
      setReason("");
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "调动申请提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTransferDecision(
    transferId: string,
    approve: boolean,
    note: string,
  ) {
    try {
      await decidePlantPersonnelTransfer(transferId, approve, note);
      setDecisionNoteFor(transferId, "");
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "调动决定失败");
    }
  }

  const selectedEmployee = employees.find((e) => e.employee_code === employeeCode);

  return (
    <section className="ledger-page">
      <header>
        <h1>本厂员工管理</h1>
        <p>查看本厂员工、发起本厂调岗或跨厂调动。跨厂调动须两厂厂长同意后交管理员执行。</p>
      </header>
      {error && <div role="alert">{error}</div>}
      {loading && <div role="status">正在加载员工数据…</div>}

      {/* 统计横幅 */}
      {employees.length > 0 && (
        <section className="ledger-stats-banner">
          <div className="ledger-stats-header">
            <strong>
              {session?.factory_name || session?.factory_id || "本厂"}人员
            </strong>
            <span className="ledger-stats-total">总人数: {employees.length}</span>
          </div>
          <div className="ledger-stats-groups">
            {Object.entries(roleGroupCounts).map(([group, count]) => (
              <span key={group} className="ledger-stats-chip">
                {group}: {count}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* 员工列表 */}
      <section>
        <div className="ledger-section-header">
          <h2>员工列表（{employees.length} 人）</h2>
          <button type="button" onClick={() => setShowTransferForm((v) => !v)}>
            {showTransferForm ? "收起" : "+ 发起调动"}
          </button>
        </div>

        {!loading && employees.length === 0 && !error && (
          <div className="ledger-empty">
            <p><strong>本厂暂未登记员工。</strong></p>
            <p className="signature-muted">请联系管理员在系统中创建员工账号并分配到本厂。</p>
          </div>
        )}

        {employees.length > 0 && (
          <div className="ledger-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>工号</th>
                  <th>姓名</th>
                  <th>当前岗位</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((emp) => {
                  const hasPending = employeePendingTransfer(emp.employee_code);
                  return (
                    <tr key={emp.employee_code}>
                      <td>{emp.employee_code}</td>
                      <td>{emp.employee_name}</td>
                      <td>{emp.role_name}</td>
                      <td>
                        {hasPending ? (
                          <span className="ledger-tag ledger-tag-stage">调动中</span>
                        ) : (
                          <span className="ledger-tag ledger-tag-done">在岗</span>
                        )}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => {
                            setEmployeeCode(emp.employee_code);
                            setToRole("");
                            setTargetFactory("");
                            setReason("");
                            setShowTransferForm(true);
                          }}
                        >
                          调岗
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 调动表单 */}
      {showTransferForm && (
        <div className="ledger-return-panel">
          <h2>发起人员调动</h2>
          <label>
            员工
            <select value={employeeCode} onChange={(event) => setEmployeeCode(event.target.value)}>
              <option value="">请选择员工</option>
              {employees.map((item) => (
                <option key={item.employee_code} value={item.employee_code}>
                  {item.employee_code} — {item.employee_name}（{item.role_name}）
                </option>
              ))}
            </select>
          </label>

          {selectedEmployee && (
            <div className="ledger-current-info">
              <p className="signature-muted">
                当前岗位：<strong>{selectedEmployee.role_name}</strong>
                {" · "}
                当前工厂：
                <strong>
                  {factories.find((f) => f.factory_id === selectedEmployee.factory_id)?.factory_name ||
                    session?.factory_name ||
                    selectedEmployee.factory_id}
                </strong>
              </p>
            </div>
          )}

          <label>
            目标岗位
            <select value={toRole} onChange={(event) => setToRole(event.target.value)}>
              <option value="">请选择目标岗位</option>
              {roles.map((item) => (
                <option key={item.role_code} value={item.role_code}>
                  {item.display_name}（{item.role_code}）
                </option>
              ))}
            </select>
          </label>

          <label>
            目标工厂（留空则为本厂调岗）
            <select value={targetFactory} onChange={(event) => setTargetFactory(event.target.value)}>
              <option value="">本厂调岗（{session?.factory_name || session?.factory_id || "当前工厂"}）</option>
              {factories.map((f) => (
                <option key={f.factory_id} value={f.factory_id}>
                  {f.factory_name}（{f.factory_id}）
                </option>
              ))}
            </select>
          </label>

          {targetFactory && selectedEmployee && (
            <div className={`ledger-transfer-type ${isIntraPlant(selectedEmployee, targetFactory) ? "ledger-transfer-intra" : "ledger-transfer-cross"}`}>
              {isIntraPlant(selectedEmployee, targetFactory)
                ? "本厂调岗 — 由你发起，提交后由管理员执行"
                : "跨厂调动 — 你发起 → 目标厂长审批 → 管理员最终执行"}
            </div>
          )}

          {/* 影响预览 */}
          {selectedEmployee && toRole && (
            <div className="ledger-impact-preview">
              <h3>影响预览</h3>
              <p>
                <strong>{selectedEmployee.employee_name}</strong>
                {" "}
                {selectedEmployee.role_name} → {roles.find((r) => r.role_code === toRole)?.display_name || toRole}
                。未来可填写：{roles.find((r) => r.role_code === toRole)?.display_name || toRole}记录。历史记录：不受影响。
              </p>
            </div>
          )}

          <label>
            调动原因
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="必填：说明调动原因"
            />
          </label>

          <div className="ledger-return-actions">
            <button
              type="button"
              disabled={!employeeCode || !toRole || !reason.trim() || submitting}
              onClick={() => void submitTransfer()}
            >
              {submitting ? "提交中…" : "提交调动申请"}
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={submitting}
              onClick={() => {
                setShowTransferForm(false);
                setEmployeeCode("");
                setToRole("");
                setTargetFactory("");
                setReason("");
              }}
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* 调动记录 */}
      <section>
        <h2>调动记录（{transfers.length} 条）</h2>
        {!loading && transfers.length === 0 && !error && (
          <div className="ledger-empty">
            <p><strong>暂无调动记录。</strong></p>
            <p className="signature-muted">发起员工调动后，记录将在此处显示。</p>
          </div>
        )}
        <div className="ledger-case-list">
          {transfers.map((item) => (
            <article key={item.transfer_id} className="ledger-transfer-item">
              <header>
                <strong>{item.employee_code} · {item.from_role} → {item.to_role}</strong>
                <span className={`ledger-tag ${
                  item.status === "REJECTED" || item.status === "CANCELLED"
                    ? "ledger-tag-alert"
                    : item.status === "APPROVED" || item.status === "EXECUTED"
                      ? "ledger-tag-done"
                      : "ledger-tag-stage"
                }`}>
                  {TRANSFER_STATUS_LABELS[item.status] ?? item.status}
                </span>
              </header>
              <p className="signature-muted">
                {item.source_factory_id} → {item.target_factory_id}
                {item.transfer_type && ` · 类型：${item.transfer_type}`}
                {item.reason && ` · 原因：${item.reason}`}
              </p>

              {/* 当前厂长（目标厂长）可审批；非目标工厂仅展示状态 */}
              {item.status === "TARGET_MANAGER_PENDING" && item.target_factory_id && (
                session?.factory_id === item.target_factory_id ? (
                  <div className="ledger-exception-actions">
                    <textarea
                      aria-label="审批意见"
                      value={getDecisionNote(item.transfer_id)}
                      onChange={(event) => setDecisionNoteFor(item.transfer_id, event.target.value)}
                      placeholder="审批意见（可选）"
                    />
                    <div className="ledger-inline-actions">
                      <button
                        type="button"
                        onClick={() => void handleTransferDecision(item.transfer_id, true, getDecisionNote(item.transfer_id) || "目标厂长同意")}
                      >
                        同意
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => void handleTransferDecision(item.transfer_id, false, getDecisionNote(item.transfer_id) || "目标厂长拒绝")}
                      >
                        拒绝
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="signature-muted">等待目标厂长审批</p>
                )
              )}
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
