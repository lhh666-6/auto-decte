import { useMemo, useState } from "react";

import {
  MobileApiError,
  mobileApiClient,
  type BambooRecord,
  type BambooStage,
} from "@form-detection/api-client";

import { getMobileDeviceId } from "../device";

export function BambooStageForm({
  record,
  stage,
  onSigned,
}: {
  record: BambooRecord;
  stage: BambooStage;
  onSigned(updated: BambooRecord): void;
}) {
  const [moisture, setMoisture] = useState(() => Array.from({ length: 8 }, () => ""));
  const [fields, setFields] = useState<Record<string, string>>({});
  const [reviewing, setReviewing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const values = useMemo<Record<string, unknown>>(() => ({
    ...(stage === "SORT" || stage === "DRYING"
      ? { moisture: moisture.filter((value) => value !== "").map(Number) }
      : {}),
    ...Object.fromEntries(Object.entries(fields).filter(([, value]) => value !== "")),
  }), [fields, moisture, stage]);

  const confirm = async () => {
    if (!navigator.onLine) {
      setError("正式签字需要联网，请恢复网络后重试。");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const updated = await mobileApiClient.submitBambooStage(
        record.record_id,
        stage,
        {
          expected_revision: record.revision,
          device_id: getMobileDeviceId(),
          values,
        },
        crypto.randomUUID(),
      );
      onSigned(updated);
    } catch (cause) {
      setError(cause instanceof MobileApiError ? cause.problem.detail : "签字提交失败，请重试。" );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="bamboo-stage-form">
      <div className="bamboo-section-title">
        <h3>{stageTitle(stage)}</h3>
        <span>第 {record.revision} 版</span>
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}

      {!reviewing ? (
        <>
          {(stage === "SORT" || stage === "DRYING") && (
            <fieldset className="bamboo-moisture-fieldset">
              <legend>含水率检测点（%）</legend>
              <div className="bamboo-moisture-grid">
                {moisture.map((value, index) => (
                  <label key={index}>
                    <span>含水率检测点 {index + 1}</span>
                    <input
                      aria-label={`含水率检测点 ${index + 1}`}
                      type="number"
                      inputMode="decimal"
                      step="0.1"
                      value={value}
                      onChange={(event) => setMoisture(moisture.map((item, itemIndex) => itemIndex === index ? event.target.value : item))}
                    />
                  </label>
                ))}
              </div>
              <div className="bamboo-point-actions">
                <button type="button" onClick={() => setMoisture([...moisture, ""])}>增加检测点</button>
                <button type="button" disabled={moisture.length <= 1} onClick={() => setMoisture(moisture.slice(0, -1))}>删除最后一个</button>
              </div>
            </fieldset>
          )}

          <div className="bamboo-field-grid">
            {stageFields(stage).map((field) => (
              <label key={field.key}>
                {field.label}
                {field.kind === "textarea" ? (
                  <textarea value={fields[field.key] ?? ""} onChange={(event) => setFields({ ...fields, [field.key]: event.target.value })} />
                ) : (
                  <input type={field.kind} inputMode={field.kind === "number" ? "decimal" : undefined} value={fields[field.key] ?? ""} onChange={(event) => setFields({ ...fields, [field.key]: event.target.value })} />
                )}
              </label>
            ))}
          </div>
          <button type="button" className="bamboo-sign-button" onClick={() => setReviewing(true)}>核对并签字</button>
        </>
      ) : (
        <div className="bamboo-sign-review">
          <h4>签字前核对</h4>
          <p>签字后，本工序数据将进入下一层处理。签字记录会绑定当前账号、工厂、职务、服务器时间和数据摘要。</p>
          <dl>
            {Object.entries(values).map(([key, value]) => (
              <div key={key}><dt>{key}</dt><dd>{Array.isArray(value) ? value.join("、") || "—" : String(value)}</dd></div>
            ))}
          </dl>
          <div className="bamboo-review-actions">
            <button type="button" onClick={() => setReviewing(false)}>返回修改</button>
            <button type="button" className="bamboo-sign-button" disabled={submitting} onClick={() => void confirm()}>{submitting ? "签字中…" : "确认签字"}</button>
          </div>
        </div>
      )}
    </section>
  );
}

function stageTitle(stage: BambooStage): string {
  return ({
    SORT: "填写分选记录",
    DIPPING: "填写浸胶记录",
    DRYING: "填写干燥记录",
    SUPERVISOR: "主管审核与签字",
    PLANT_AUDIT: "厂长审核与签字",
  })[stage];
}

function stageFields(stage: BambooStage): Array<{ key: string; label: string; kind: "text" | "number" | "datetime-local" | "textarea" }> {
  switch (stage) {
    case "SORT":
      return [{ key: "sort_quantity", label: "分选数量", kind: "number" }, { key: "wage_amount", label: "分选工资（签字后锁定）", kind: "number" }, { key: "note", label: "分选备注", kind: "textarea" }];
    case "DIPPING":
      return [{ key: "glue_batch", label: "胶液批次", kind: "text" }, { key: "glue_gain", label: "浸胶计件量", kind: "number" }, { key: "wage_amount", label: "浸胶工资分配", kind: "number" }, { key: "started_at", label: "浸胶开始时间", kind: "datetime-local" }, { key: "ended_at", label: "浸胶结束时间", kind: "datetime-local" }, { key: "note", label: "浸胶备注", kind: "textarea" }];
    case "DRYING":
      return [{ key: "rack_no", label: "干燥架号", kind: "text" }, { key: "rack_count", label: "干燥计件量", kind: "number" }, { key: "wage_amount", label: "干燥工资分配（与浸胶联合生效）", kind: "number" }, { key: "started_at", label: "干燥开始时间", kind: "datetime-local" }, { key: "ended_at", label: "干燥结束时间", kind: "datetime-local" }, { key: "note", label: "干燥备注", kind: "textarea" }];
    case "SUPERVISOR":
      return [{ key: "conclusion", label: "主管审核结论", kind: "text" }, { key: "note", label: "审核说明", kind: "textarea" }];
    case "PLANT_AUDIT":
      return [{ key: "conclusion", label: "厂长审核结论", kind: "text" }, { key: "note", label: "审核说明", kind: "textarea" }];
  }
}
