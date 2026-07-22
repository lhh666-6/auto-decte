import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  MobileApiError,
  mobileApiClient,
  type BambooRecord,
  type BambooStage,
} from "@form-detection/api-client";

import { useMobileSession } from "../session/MobileSessionProvider";
import { BambooStageForm } from "./BambooStageForm";
import { BambooOperationsPanel } from "./BambooOperationsPanel";

const FLOW: Array<{ stage: BambooStage; label: string }> = [
  { stage: "SORT", label: "分选" },
  { stage: "DIPPING", label: "浸胶" },
  { stage: "DRYING", label: "干燥" },
  { stage: "SUPERVISOR", label: "主管" },
  { stage: "PLANT_AUDIT", label: "厂长" },
];

const ROLE_STAGE: Record<string, BambooStage> = {
  SORT_OPERATOR: "SORT",
  DIPPING_OPERATOR: "DIPPING",
  DRYING_RACK_OPERATOR: "DRYING",
  SUPERVISOR: "SUPERVISOR",
  PLANT_MANAGER: "PLANT_AUDIT",
};

export function BambooRecordDetailPage({ recordId }: { recordId: string }) {
  const { sessionMetadata: session } = useMobileSession();
  const [record, setRecord] = useState<BambooRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRecord(await mobileApiClient.getBambooRecord(recordId));
    } catch (cause) {
      setError(cause instanceof MobileApiError ? cause.problem.detail : "无法加载竹丝工序记录。" );
    } finally {
      setLoading(false);
    }
  }, [recordId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <div className="mobile-page"><div className="mobile-loading">加载记录中…</div></div>;
  if (!record) return <div className="mobile-page"><div className="error-banner" role="alert">{error || "记录不可见"}</div></div>;

  const completedStages = new Set(record.submissions.map((submission) => submission.stage));
  const canSign = record.current_stage !== null
    && ROLE_STAGE[session?.bamboo_role ?? ""] === record.current_stage;

  return (
    <div className="mobile-page bamboo-detail-page">
      <header className="mobile-page-header">
        <Link to="/mobile/record/bamboo-process" className="text-button">← 返回任务</Link>
        <h2>竹丝工序记录</h2>
      </header>
      {error && <div className="error-banner" role="alert">{error}</div>}

      <section className="bamboo-record-hero">
        <div><span>记录编号</span><strong>{record.display_no}</strong></div>
        <em>{record.status === "COMPLETED" ? "已完成" : "进行中"}</em>
      </section>

      <ol className="bamboo-flow-strip" aria-label="工序进度">
        {FLOW.map((item) => (
          <li
            key={item.stage}
            className={completedStages.has(item.stage) ? "done" : record.current_stage === item.stage ? "current" : ""}
          >
            <i aria-hidden="true">{completedStages.has(item.stage) ? "✓" : FLOW.findIndex((entry) => entry.stage === item.stage) + 1}</i>
            <span>{item.label}</span>
          </li>
        ))}
      </ol>

      <section className="bamboo-sheet-section">
        <h3>基础信息</h3>
        <dl className="bamboo-sheet-grid">
          {Object.entries(record.base_info).map(([key, value]) => (
            <div key={key}><dt>{baseLabel(key)}</dt><dd>{String(value ?? "—")}</dd></div>
          ))}
        </dl>
      </section>

      {record.submissions.map((submission) => (
        <section className="bamboo-sheet-section" key={submission.submission_id}>
          <div className="bamboo-section-title">
            <h3>{FLOW.find((item) => item.stage === submission.stage)?.label}记录</h3>
            <span>已由 {submission.actor_name} 签字</span>
          </div>
          <dl className="bamboo-sheet-grid">
            {Object.entries(submission.values).map(([key, value]) => (
              <div key={key}><dt>{valueLabel(key)}</dt><dd>{formatValue(value)}</dd></div>
            ))}
          </dl>
        </section>
      ))}

      <BambooOperationsPanel
        record={record}
        role={session?.bamboo_role ?? ""}
        onRefresh={load}
      />

      {canSign && record.current_stage && (
        <BambooStageForm
          record={record}
          stage={record.current_stage}
          onSigned={(updated) => setRecord(updated)}
        />
      )}
    </div>
  );
}

function baseLabel(key: string): string {
  return ({ cage_no: "竹笼号", length: "长度", grade: "等级", bundle_count: "捆数" } as Record<string, string>)[key] ?? key;
}

function valueLabel(key: string): string {
  return ({
    moisture: "含水率检测点",
    sort_quantity: "分选数量",
    note: "备注",
    glue_batch: "胶液批次",
    started_at: "开始时间",
    ended_at: "结束时间",
    rack_no: "干燥架号",
    conclusion: "审核结论",
  } as Record<string, string>)[key] ?? key;
}

function formatValue(value: unknown): string {
  return Array.isArray(value) ? value.join("、") : String(value ?? "—");
}
