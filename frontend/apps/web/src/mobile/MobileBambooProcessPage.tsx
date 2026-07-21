import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { MobileApiError, mobileApiClient, type MobileActiveResource } from "@form-detection/api-client";
import { getMobileDeviceId } from "./device";
import { useMobileSession } from "./session/MobileSessionProvider";
import { submitWithOutbox } from "./sync/SubmissionCoordinator";

/**
 * Three-step bamboo cage process recording form.
 * Step 1: Pick process → Step 2: Pick cage → Step 3: Fill & submit
 */
export function MobileBambooProcessPage() {
  const navigate = useNavigate();
  const { sessionMetadata } = useMobileSession();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedProcess, setSelectedProcess] = useState("");
  const [selectedCage, setSelectedCage] = useState<MobileActiveResource | null>(null);
  const [cages, setCages] = useState<MobileActiveResource[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [definitionVersionId, setDefinitionVersionId] = useState("");
  const [editableFields, setEditableFields] = useState<string[]>([]);

  // Form field values
  const [moisture, setMoisture] = useState("");
  const [rackNo, setRackNo] = useState("");
  const [result, setResult] = useState<"NORMAL" | "EXCEPTION" | "">("");
  const [exceptionType, setExceptionType] = useState("");
  const [exceptionNote, setExceptionNote] = useState("");

  const processes = ["SORTING", "DIPPING", "DRYING_RACK", "INSPECTION"] as const;
  const processLabels: Record<string, string> = {
    SORTING: "分选",
    DIPPING: "浸胶",
    DRYING_RACK: "干燥装架",
    INSPECTION: "检测复核",
  };

  const exceptionTypes = ["含水率异常", "装笼异常", "架号不符", "材料异常", "设备异常", "其他"];

  useEffect(() => {
    mobileApiClient.getFormSchema("BAMBOO_PROCESS_RECORD")
      .then((schema) => {
        setDefinitionVersionId(schema.definition_version_id);
        setEditableFields(schema.fields.filter((field) => field.editable).map((field) => field.field_name));
      })
      .catch((cause: unknown) => {
        setError(cause instanceof MobileApiError ? cause.problem.detail : "无法加载表单定义，请重试。");
      });
  }, []);

  // Load cages after process selected
  const loadCages = useCallback(async (processCode: string) => {
    setLoading(true);
    setError("");
    try {
      const data = await mobileApiClient.getActiveResources("CAGE", processCode);
      setCages(data.resources);
    } catch (cause) {
      setCages([]);
      setError(cause instanceof MobileApiError
        ? cause.problem.detail
        : "无法加载可用竹丝笼，请检查网络后重试。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (step === 2 && selectedProcess) loadCages(selectedProcess);
  }, [step, selectedProcess, loadCages]);

  const submit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!selectedProcess || !selectedCage) return;
      setSubmitting(true);
      setError("");
      try {
        if (!sessionMetadata || !definitionVersionId) throw new Error("表单尚未准备完成，请重试。");
        const candidateValues: Record<string, unknown> = {
          process_code: selectedProcess,
          resource_id: selectedCage.resource_id,
          moisture,
          rack_no: rackNo,
          result: result || "NORMAL",
          exception_type: exceptionType || null,
          exception_note: exceptionNote || null,
        };
        const values = Object.fromEntries(
          editableFields
            .filter((fieldName) => fieldName in candidateValues)
            .map((fieldName) => [fieldName, candidateValues[fieldName]]),
        );
        const receipt = await submitWithOutbox({
          form_type: "BAMBOO_PROCESS_RECORD",
          definition_version_id: definitionVersionId,
          mode: "SELF",
          subject_employee_code: sessionMetadata.employee_code,
          device_id: getMobileDeviceId(),
          values,
        }, crypto.randomUUID());
        navigate(receipt ? "/mobile/submissions" : "/mobile/outbox", { replace: true });
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "提交失败，请重试。");
      } finally {
        setSubmitting(false);
      }
    },
    [definitionVersionId, editableFields, exceptionNote, exceptionType, moisture, navigate, rackNo, result, selectedCage, selectedProcess, sessionMetadata],
  );

  return (
    <div className="mobile-page">
      <header className="mobile-page-header">
        {step > 1 && (
          <button type="button" className="text-button" onClick={() => setStep((s) => (s - 1) as 1 | 2 | 3)}>
            ← 上一步
          </button>
        )}
        <h2>竹丝工序记录</h2>
        <span className="mobile-step-indicator">步骤 {step}/3</span>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}

      {/* Step 1: Select process */}
      {step === 1 && (
        <section className="mobile-step-body">
          <p className="mobile-step-hint">请选择刚完成的工序</p>
          <div className="mobile-process-grid">
            {processes.map((p) => (
              <button
                key={p}
                type="button"
                className={`mobile-process-button${selectedProcess === p ? " active" : ""}`}
                onClick={() => { setSelectedProcess(p); setStep(2); }}
              >
                {processLabels[p]}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Step 2: Select cage */}
      {step === 2 && (
        <section className="mobile-step-body">
          <p className="mobile-step-hint">选择本次操作的竹丝笼</p>
          {loading ? (
            <div className="mobile-loading">加载中…</div>
          ) : cages.length === 0 ? (
            <div className="mobile-empty">
              <p>暂无可操作的竹丝笼</p>
            </div>
          ) : (
            <ul className="mobile-cage-list">
              {cages.map((cage) => (
                <li key={cage.resource_id}>
                  <button
                    type="button"
                    className={`mobile-cage-card${selectedCage?.resource_id === cage.resource_id ? " active" : ""}`}
                    onClick={() => { setSelectedCage(cage); setStep(3); }}
                  >
                    <strong>{cage.short_code}</strong>
                    <span>{cage.variety} · {cage.grade} · {cage.supplier}</span>
                    <small>上一工序：{processLabels[cage.last_process] ?? cage.last_process} {cage.last_process_time}</small>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Step 3: Fill and submit */}
      {step === 3 && selectedCage && (
        <form className="mobile-step-body mobile-fill-form" onSubmit={submit}>
          {/* Read-only context */}
          <div className="mobile-readonly-section">
            <div className="mobile-readonly-row">
              <span>短笼号</span><strong>{selectedCage.short_code}</strong>
            </div>
            <div className="mobile-readonly-row">
              <span>品种</span><strong>{selectedCage.variety} · {selectedCage.grade}</strong>
            </div>
            <div className="mobile-readonly-row">
              <span>供应商</span><strong>{selectedCage.supplier}</strong>
            </div>
            <div className="mobile-readonly-row">
              <span>本次工序</span><strong>{processLabels[selectedProcess]}</strong>
            </div>
          </div>

          {/* Editable fields */}
          <label>
            <span>含水率 (%)</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              value={moisture}
              onChange={(e) => setMoisture(e.target.value)}
            />
          </label>

          {selectedProcess === "DRYING_RACK" && (
            <label>
              <span>干燥架号</span>
              <input
                type="text"
                value={rackNo}
                onChange={(e) => setRackNo(e.target.value)}
                placeholder="如：架-03"
              />
            </label>
          )}

          {/* Result preset */}
          <fieldset className="mobile-preset-group">
            <legend>结果</legend>
            <div className="mobile-preset-buttons">
              {(["NORMAL", "EXCEPTION"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  className={`mobile-preset-button${result === v ? " active" : ""}`}
                  onClick={() => setResult(v)}
                >
                  {v === "NORMAL" ? "正常" : "异常"}
                </button>
              ))}
            </div>
          </fieldset>

          {/* Conditional: exception details */}
          {result === "EXCEPTION" && (
            <>
              <fieldset className="mobile-preset-group">
                <legend>异常类型</legend>
                <div className="mobile-preset-chips">
                  {exceptionTypes.map((t) => (
                    <button
                      key={t}
                      type="button"
                      className={`mobile-preset-chip${exceptionType === t ? " active" : ""}`}
                      onClick={() => setExceptionType(t === exceptionType ? "" : t)}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </fieldset>
              <label>
                <span>异常说明</span>
                <textarea
                  rows={3}
                  value={exceptionNote}
                  onChange={(e) => setExceptionNote(e.target.value)}
                  placeholder="请描述异常情况（≤100字）"
                  maxLength={100}
                />
              </label>
            </>
          )}

          <div className="mobile-form-actions">
            <button type="submit" className="button button-primary" disabled={submitting}>
              {submitting ? "提交中…" : "提交"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
