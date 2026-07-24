import { useEffect, useMemo, useRef, useState } from "react";

import {
  MobileApiError,
  mobileApiClient,
  type BambooRecord,
  type BambooStage,
} from "@form-detection/api-client";

import { createMobileClientId, getMobileDeviceId } from "../device";
import { useMobileSession } from "../session/MobileSessionProvider";
import { clearBambooDraft, readBambooDraft, writeBambooDraft, type BambooDraftScope } from "../storage/bambooDrafts";

type StageDraft = { moisture: string[]; fields: Record<string, string>; rackNumbers: string[] };

export function BambooStageForm({
  record,
  stage,
  onSigned,
  unresolvedExceptions = false,
}: {
  record: BambooRecord;
  stage: BambooStage;
  onSigned(updated: BambooRecord): void;
  unresolvedExceptions?: boolean;
}) {
  const { sessionMetadata: session } = useMobileSession();
  const [moisture, setMoisture] = useState(() => Array.from({ length: 8 }, () => ""));
  const [fields, setFields] = useState<Record<string, string>>({});
  const [rackNumbers, setRackNumbers] = useState([""]);
  const [reviewing, setReviewing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [idempotencyKey] = useState(() => createMobileClientId(`stage-${stage.toLowerCase()}`));
  const restoredKey = useRef("");
  const draftScope = useMemo<BambooDraftScope | null>(() => session ? ({
    employeeCode: session.employee_code,
    factoryId: session.factory_id,
    deviceId: getMobileDeviceId(),
    recordId: record.record_id,
    stage,
  }) : null, [record.record_id, session, stage]);

  useEffect(() => {
    if (!draftScope) return;
    const key = JSON.stringify(draftScope);
    if (restoredKey.current === key) return;
    restoredKey.current = key;
    const draft = readBambooDraft<StageDraft>(draftScope);
    if (!draft) return;
    if (Array.isArray(draft.moisture)) setMoisture(draft.moisture);
    if (draft.fields && typeof draft.fields === "object") setFields(draft.fields);
    if (Array.isArray(draft.rackNumbers)) setRackNumbers(draft.rackNumbers);
  }, [draftScope]);

  useEffect(() => {
    if (!draftScope || restoredKey.current !== JSON.stringify(draftScope)) return;
    writeBambooDraft(draftScope, { moisture, fields, rackNumbers });
  }, [draftScope, fields, moisture, rackNumbers]);

  const moistureValues = useMemo(
    () => moisture.filter((value) => value.trim() !== "").map(Number),
    [moisture],
  );
  const moistureAverage = useMemo(
    () => moistureValues.length
      ? (moistureValues.reduce((total, value) => total + value, 0) / moistureValues.length).toFixed(1)
      : null,
    [moistureValues],
  );
  const normalizedRacks = useMemo(
    () => rackNumbers.map((value) => value.trim()).filter(Boolean),
    [rackNumbers],
  );
  const values = useMemo<Record<string, unknown>>(() => ({
    ...(isProductionStage(stage) ? { moisture: moistureValues } : { conclusion: "APPROVED" }),
    ...(stage === "DRYING" ? { rack_numbers: normalizedRacks } : {}),
    ...Object.fromEntries(Object.entries(fields).filter(([, value]) => value.trim() !== "")),
  }), [fields, moistureValues, normalizedRacks, stage]);

  const requestReview = () => {
    const validation = validate(stage, moisture, normalizedRacks, fields);
    if (validation) {
      setError(validation);
      return;
    }
    setError("");
    setReviewing(true);
  };

  const confirm = async () => {
    if (!navigator.onLine) {
      setError("正式签字需要联网，请恢复网络后重试。");
      setReviewing(false);
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
        idempotencyKey,
      );
      if (draftScope) clearBambooDraft(draftScope);
      setReviewing(false);
      onSigned(updated);
    } catch (cause) {
      setError(cause instanceof MobileApiError ? cause.problem.detail : "签字提交失败，请重试。" );
      setReviewing(false);
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
      <div className="bamboo-sign-identity">
        <strong>{session?.employee_name || "当前登录人员"}</strong>
        <span>{session?.team_name || "当前班组"} · {session?.position || roleLabel(session?.bamboo_role)}</span>
        <small>身份、班组、工厂和服务器签字时间由系统带出并绑定，不可代签。</small>
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}

      {isProductionStage(stage) && (
        <fieldset className="bamboo-moisture-fieldset">
          <legend>含水率检测点（%）</legend>
          <div className="bamboo-moisture-grid">
            {moisture.map((value, index) => (
              <label key={index}>
                <span>检测点 {index + 1}</span>
                <input
                  aria-label={`含水率检测点 ${index + 1}`}
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  placeholder="1-100"
                  value={value}
                  onChange={(event) => setMoisture(moisture.map((item, itemIndex) => itemIndex === index ? event.target.value : item))}
                />
              </label>
            ))}
          </div>
          <div className="bamboo-point-actions">
            <button type="button" disabled={moisture.length >= 20} onClick={() => setMoisture([...moisture, ""])}>增加检测点</button>
            <button type="button" disabled={moisture.length <= 1} onClick={() => setMoisture(moisture.slice(0, -1))}>删除最后一个</button>
          </div>
          <p className="bamboo-moisture-average">已填写 {moistureValues.length} 点 · 平均值 {moistureAverage ?? "—"}%</p>
        </fieldset>
      )}

      {stage === "DRYING" && (
        <fieldset className="bamboo-moisture-fieldset bamboo-rack-fieldset">
          <legend>干燥架号</legend>
          <div className="bamboo-rack-list">
            {rackNumbers.map((rack, index) => <label key={index}><span>架号 {index + 1}</span><input value={rack} placeholder="如：G-01" onChange={(event) => setRackNumbers(rackNumbers.map((item, itemIndex) => itemIndex === index ? event.target.value : item))} /></label>)}
          </div>
          <div className="bamboo-point-actions">
            <button type="button" onClick={() => setRackNumbers([...rackNumbers, ""])}>添加架号</button>
            <button type="button" disabled={rackNumbers.length <= 1} onClick={() => setRackNumbers(rackNumbers.slice(0, -1))}>删除最后一个</button>
          </div>
        </fieldset>
      )}

      {isReviewStage(stage) && (
        <div className="bamboo-upstream-review">
          <strong>已展示完整上游记录</strong>
          <p>请核对本页基础字段、来源快照、所有生产提交及检测留痕后再签字。主管评价可选填。</p>
        </div>
      )}

      <div className="bamboo-field-grid">
        {stageFields(stage).map((field) => (
          <label key={field.key}>
            {field.label}{field.optional && <small>（选填）</small>}
            {field.kind === "textarea" ? (
              <textarea value={fields[field.key] ?? ""} onChange={(event) => setFields({ ...fields, [field.key]: event.target.value })} />
            ) : (
              <input type={field.kind} inputMode={field.numeric ? "decimal" : undefined} value={fields[field.key] ?? ""} onChange={(event) => setFields({ ...fields, [field.key]: event.target.value })} />
            )}
          </label>
        ))}
      </div>
      {stage === "SUPERVISOR" && unresolvedExceptions && <div className="error-banner" role="alert">存在未关闭的检测异常，请先处理后再签字</div>}
      <button type="button" className="bamboo-sign-button" onClick={requestReview}>{primaryLabel(stage)}</button>

      {reviewing && (
        <div className="bamboo-v3-sheet-backdrop" role="presentation">
          <div className="bamboo-v3-bottom-sheet bamboo-stage-confirm-sheet" role="dialog" aria-modal="true" aria-labelledby="stageConfirmTitle">
            <div className="bamboo-v3-sheet-handle" />
            <header><h3 id="stageConfirmTitle">签字前核对</h3><button type="button" aria-label="关闭" onClick={() => setReviewing(false)} disabled={submitting}>×</button></header>
            <div className="banner info">本次签字将绑定 {session?.employee_name || "当前账号"}、{session?.factory_name || "当前工厂"}、职务、服务器时间和数据摘要。</div>
            <dl className="bamboo-sheet-grid bamboo-confirm-values">
              {Object.entries(values).map(([key, value]) => <div key={key}><dt>{valueLabel(key)}</dt><dd>{formatValue(value)}</dd></div>)}
            </dl>
            <div className="btnrow">
              <button type="button" className="btn secondary" onClick={() => setReviewing(false)} disabled={submitting}>返回修改</button>
              <button type="button" className="btn primary" onClick={() => void confirm()} disabled={submitting}>{submitting ? "签字中…" : confirmLabel(stage)}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

type StageField = { key: string; label: string; kind: "text" | "datetime-local" | "textarea"; numeric?: boolean; optional?: boolean };

function stageTitle(stage: BambooStage): string {
  return ({ SORT: "重填分选记录", DIPPING: "填写浸胶记录", DRYING: "填写干燥并联合签字", SUPERVISOR: "主管审核", PLANT_AUDIT: "厂长审核" })[stage];
}
function stageFields(stage: BambooStage): StageField[] {
  switch (stage) {
    case "SORT": return [{ key: "note", label: "分选备注", kind: "textarea", optional: true }];
    case "DIPPING": return [
      { key: "glue_before_weight", label: "胶前重", kind: "text", numeric: true, optional: true },
      { key: "glue_after_weight", label: "胶后重", kind: "text", numeric: true, optional: true },
      { key: "glue_gain", label: "上胶量", kind: "text", numeric: true, optional: true },
      { key: "glue_batch", label: "胶液批次", kind: "text", optional: true },
      { key: "started_at", label: "浸胶开始时间", kind: "datetime-local", optional: true },
      { key: "ended_at", label: "浸胶结束时间", kind: "datetime-local", optional: true },
      { key: "note", label: "浸胶备注", kind: "textarea", optional: true },
    ];
    case "DRYING": return [
      { key: "started_at", label: "干燥开始时间", kind: "datetime-local", optional: true },
      { key: "ended_at", label: "干燥结束时间", kind: "datetime-local", optional: true },
      { key: "note", label: "干燥备注", kind: "textarea", optional: true },
    ];
    case "SUPERVISOR": return [{ key: "note", label: "主管评价", kind: "textarea", optional: true }];
    case "PLANT_AUDIT": return [{ key: "note", label: "厂长审核说明", kind: "textarea", optional: true }];
  }
}
function validate(stage: BambooStage, moisture: string[], racks: string[], fields: Record<string, string>): string {
  if (isProductionStage(stage)) {
    const filled = moisture.filter((value) => value.trim() !== "");
    if (!filled.length) return "请至少填写一个含水率检测点";
    if (filled.some((value) => !/^\d+$/.test(value.trim()) || Number(value) < 1 || Number(value) > 100)) return "含水率需填写 1 至 100 的正整数";
  }
  if (stage === "DRYING") {
    if (!racks.length) return "请至少填写一个干燥架号";
    if (new Set(racks).size !== racks.length) return "干燥架号不能重复";
  }
  if (stage === "DIPPING") {
    for (const key of ["glue_before_weight", "glue_after_weight", "glue_gain"]) {
      const value = fields[key]?.trim();
      if (value && (!Number.isFinite(Number(value)) || Number(value) < 0)) return "浸胶重量和上胶量需填写非负数字";
    }
    const before = fields.glue_before_weight?.trim();
    const after = fields.glue_after_weight?.trim();
    if (before && after && Number(after) < Number(before)) return "胶后重不能小于胶前重";
  }
  return "";
}
function isProductionStage(stage: BambooStage): boolean { return stage === "SORT" || stage === "DIPPING" || stage === "DRYING"; }
function isReviewStage(stage: BambooStage): boolean { return stage === "SUPERVISOR" || stage === "PLANT_AUDIT"; }
function primaryLabel(stage: BambooStage): string { return isReviewStage(stage) ? "通过并签字" : stage === "DRYING" ? "核对并提交干燥联合签字" : `核对并提交${stage === "SORT" ? "分选" : "浸胶"}记录`; }
function confirmLabel(stage: BambooStage): string { return isReviewStage(stage) ? "通过并签字" : "确认提交"; }
function roleLabel(role = ""): string { return ({ SORT_OPERATOR: "分选工", DIPPING_OPERATOR: "浸胶工", DRYING_RACK_OPERATOR: "干燥工", SUPERVISOR: "主管", PLANT_MANAGER: "厂长" } as Record<string, string>)[role] ?? role; }
function valueLabel(key: string): string { return ({ moisture: "含水率检测点", conclusion: "审核结论", note: "备注/评价", glue_before_weight: "胶前重", glue_after_weight: "胶后重", glue_gain: "上胶量", glue_batch: "胶液批次", rack_numbers: "干燥架号", started_at: "开始时间", ended_at: "结束时间" } as Record<string, string>)[key] ?? key; }
function formatValue(value: unknown): string { return Array.isArray(value) ? value.join("、") || "—" : String(value ?? "—"); }
