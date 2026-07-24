import { useState } from "react";
import type { FormEvent } from "react";

import {
  confirmDiscoveryRules,
  createDiscoverySession,
  sendDiscoveryMessage,
} from "./api";
import type { ProposedBusinessRule } from "./types";
import { StatusBadge, PageHeader, ErrorAlert, SummaryCardGrid } from "./shared";
import type { SummaryCard } from "./shared";
import "./workflow-designer.css";
import "./finance-pages.css";

interface BusinessModule {
  key: string;
  title: string;
  description: string;
  status: "配置完成" | "待配置" | "部分配置";
  lastModified: string;
}

interface ClosureRule {
  name: string;
  scope: string;
  inputs: string[];
  expression: string;
  tolerance: string;
  failLevel: "阻断" | "警告";
}

const MODULES: BusinessModule[] = [
  {
    key: "metering",
    title: "计量口径",
    description: "定义工资计算中的计量单位、换算系数和舍入规则。",
    status: "配置完成",
    lastModified: "2026-07-22 14:30",
  },
  {
    key: "master_data",
    title: "主数据关系",
    description: "员工、工厂、岗位、角色和表单类型之间的数据关联约束。",
    status: "配置完成",
    lastModified: "2026-07-22 10:15",
  },
  {
    key: "closure_rules",
    title: "数量闭合规则",
    description: "输入与输出变量的数量关系约束、容差和失败处理策略。",
    status: "部分配置",
    lastModified: "2026-07-21 16:45",
  },
  {
    key: "source_priority",
    title: "来源优先级",
    description: "当同一数据存在多个来源时，定义优先采用顺序和冲突解决策略。",
    status: "待配置",
    lastModified: "—",
  },
  {
    key: "payroll_fact",
    title: "工资事实来源",
    description: "Bamboo 生产记录、工时事实和外部数据如何映射到工资计算事实。",
    status: "配置完成",
    lastModified: "2026-07-22 08:00",
  },
  {
    key: "business_object",
    title: "业务对象关系",
    description: "表单、工作流、记录、员工和工厂之间的业务对象依赖和生命周期。",
    status: "配置完成",
    lastModified: "2026-07-20 11:20",
  },
  {
    key: "effective_scope",
    title: "生效范围",
    description: "规则适用的工厂、岗位、时间范围和条件限制。",
    status: "部分配置",
    lastModified: "2026-07-23 09:10",
  },
];

const SAMPLE_CLOSURE_RULES: ClosureRule[] = [
  {
    name: "装架工资合计闭合",
    scope: "装架组工资计算 / 热压工厂",
    inputs: ["装架数量 × 单价", "班组分配系数", "加班补贴"],
    expression: "ABS(SUM(分项) - 总工资) ≤ 容差 × SUM(分项)",
    tolerance: "0.001 (0.1%)",
    failLevel: "阻断",
  },
  {
    name: "计时工工时闭合",
    scope: "计时工日工资 / 所有工厂",
    inputs: ["计时登记工时", "生产记录工时", "厂内调整"],
    expression: "合计工时 = 登记工时 + 调整工时",
    tolerance: "0.5 小时",
    failLevel: "警告",
  },
  {
    name: "蒸煮产量原料闭合",
    scope: "蒸煮岗位 / 蒸煮车间",
    inputs: ["原料投入量", "产出量", "损耗量"],
    expression: "投入量 = 产出量 + 损耗量",
    tolerance: "0.01 (1%)",
    failLevel: "阻断",
  },
];

function moduleStatusBadge(status: string) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 10,
        fontSize: 11,
        fontWeight: 650,
        color: status === "配置完成" ? "#1a6b3c" : status === "部分配置" ? "#8a6300" : "#596579",
        background: status === "配置完成" ? "#d4edda" : status === "部分配置" ? "#fff3cd" : "#e8ecf1",
      }}
    >
      {status}
    </span>
  );
}

export function BusinessModelingPage() {
  const [sessionId, setSessionId] = useState("");
  const [rules, setRules] = useState<ProposedBusinessRule[]>([]);
  const [message, setMessage] = useState("");
  const [baseline, setBaseline] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [showClosureRules, setShowClosureRules] = useState(false);

  function reload() {
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const activeSession = sessionId
        ? { session_id: sessionId }
        : await createDiscoverySession("财务业务逻辑梳理");
      setSessionId(activeSession.session_id);
      const result = await sendDiscoveryMessage(activeSession.session_id, message);
      setRules((current) => [...current, ...result.proposed_rules]);
      setMessage("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "业务梳理失败");
    }
  }

  async function confirm() {
    try {
      const result = await confirmDiscoveryRules(
        sessionId,
        rules.map((rule) => rule.rule_id),
      );
      setBaseline(result.baseline.version);
      setRules((current) =>
        current.map((rule) => ({
          ...rule,
          status: "CONFIRMED",
          executable: true,
        })),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "确认失败");
    }
  }

  const overviewCards: SummaryCard[] = [
    { key: "modules", label: "业务模块", value: MODULES.length },
    { key: "configured", label: "已配置模块", value: MODULES.filter((m) => m.status === "配置完成").length },
    { key: "rules", label: "发现规则", value: rules.length },
    { key: "baseline", label: "基线版本", value: baseline ?? "—" },
  ];

  return (
    <section className="business-model-page">
      <PageHeader title="业务建模" subtitle="系统只生成待确认草稿；未经财务确认的规则不会参与执行。" />

      {error && <ErrorAlert message={error} onRetry={reload} />}

      {/* Overview cards */}
      <SummaryCardGrid cards={overviewCards} />

      {/* Business module cards */}
      <h2 style={{ margin: 0, fontSize: 15 }}>业务配置模块</h2>
      <div className="business-module-grid">
        {MODULES.map((mod) => (
          <div
            key={mod.key}
            className="business-module-card"
            onClick={() => {
              if (mod.key === "closure_rules") setShowClosureRules(true);
            }}
          >
            <h3>{mod.title}</h3>
            <p>{mod.description}</p>
            <div className="business-module-meta">
              {moduleStatusBadge(mod.status)}
              <span>修改: {mod.lastModified}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Quantity closure rules section */}
      {showClosureRules && (
        <div className="closure-rules-section">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2>数量闭合规则</h2>
            <button
              type="button"
              onClick={() => setShowClosureRules(false)}
              style={{ padding: "4px 10px", border: "1px solid #b9c6d5", borderRadius: 4, background: "#fff", cursor: "pointer", fontSize: 12 }}
            >
              关闭
            </button>
          </div>
          {SAMPLE_CLOSURE_RULES.map((rule) => (
            <div key={rule.name} className="closure-rule-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3>{rule.name}</h3>
                <span
                  className={`closure-rule-fail-level ${rule.failLevel === "阻断" ? "closure-rule-fail-block" : "closure-rule-fail-warn"}`}
                >
                  {rule.failLevel}
                </span>
              </div>
              <div className="closure-rule-meta">
                <span>适用范围: {rule.scope}</span>
              </div>
              <div style={{ display: "grid", gap: 4, fontSize: 13 }}>
                <div>
                  <span style={{ color: "#596579" }}>输入变量: </span>
                  {rule.inputs.map((inp, i) => (
                    <span key={i} style={{ marginRight: 8, background: "#f0f3f7", padding: "1px 6px", borderRadius: 4, fontSize: 12 }}>{inp}</span>
                  ))}
                </div>
                <div>
                  <span style={{ color: "#596579" }}>关系表达式:</span>
                  <div className="closure-rule-expression">{rule.expression}</div>
                </div>
                <div className="closure-rule-meta">
                  <span>容差: {rule.tolerance}</span>
                  <span>失败级别: {rule.failLevel}</span>
                </div>
              </div>
            </div>
          ))}
          {SAMPLE_CLOSURE_RULES.length === 0 && (
            <p style={{ color: "#596579", fontSize: 13 }}>暂无闭合规则配置。</p>
          )}
        </div>
      )}

      {/* Discovery form */}
      <form className="business-discovery-form" onSubmit={submit} style={{ display: "grid", gap: 8, background: "#fff", border: "1px solid #dce3ec", borderRadius: 12, padding: 16 }}>
        <label style={{ display: "grid", gap: 4, fontSize: 13, color: "#42566f" }}>
          描述现有业务规则
          <textarea
            aria-label="业务说明"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            required
            style={{ padding: "8px 10px", border: "1px solid #b9c6d5", borderRadius: 6, font: "inherit", fontSize: 13, resize: "vertical", minHeight: 80 }}
          />
        </label>
        <button
          type="submit"
          style={{ justifySelf: "start", padding: "8px 16px", border: 0, borderRadius: 6, color: "#fff", background: "#155eef", font: "inherit", fontSize: 13, fontWeight: 650, cursor: "pointer" }}
        >
          生成待确认规则
        </button>
      </form>

      {/* Discovered rules list */}
      {rules.length > 0 && (
        <>
          <h2 style={{ margin: 0, fontSize: 15 }}>待确认规则 ({rules.length})</h2>
          <div className="workflow-card-list" style={{ display: "grid", gap: 8 }}>
            {rules.map((rule) => (
              <article key={rule.rule_id} className="workflow-node-card" style={{ cursor: "default" }}>
                <span
                  className="workflow-node-index"
                  style={{
                    background: rule.executable ? "#d4edda" : "#fef3e4",
                    color: rule.executable ? "#1a6b3c" : "#8a6300",
                    width: 32, height: 32, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "50%", fontWeight: 700, fontSize: 14,
                  }}
                >
                  {rule.executable ? "OK" : "!"}
                </span>
                <div className="workflow-node-info">
                  <strong>{rule.content_json.statement}</strong>
                  <span style={{ color: rule.status === "CONFIRMED" ? "#1a6b3c" : "#8a6300", fontSize: 12 }}>
                    {rule.status === "CONFIRMED" ? "财务已确认" : "不可执行草稿"}
                  </span>
                  <small style={{ color: "#596579" }}>建议置信度 {rule.confidence}%</small>
                </div>
                <StatusBadge status={rule.status} />
              </article>
            ))}
          </div>
          {rules.some((rule) => !rule.executable) && (
            <button
              type="button"
              onClick={() => void confirm()}
              style={{ justifySelf: "start", padding: "8px 16px", border: 0, borderRadius: 6, color: "#fff", background: "#155eef", font: "inherit", fontSize: 13, fontWeight: 650, cursor: "pointer" }}
            >
              确认并生成业务基线
            </button>
          )}
          {baseline && (
            <p role="status" style={{ color: "#1a6b3c", fontWeight: 650, fontSize: 13 }}>
              业务基线版本 {baseline} 已确认
            </p>
          )}
        </>
      )}
    </section>
  );
}
