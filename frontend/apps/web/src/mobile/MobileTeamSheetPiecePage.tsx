import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { mobileApiClient } from "@form-detection/api-client";
import { getMobileDeviceId } from "./device";
import { MobileFormEngine } from "./MobileFormEngine";
import { useMobileSession } from "./session/MobileSessionProvider";
import { saveDraft } from "./storage/drafts";
import { submitWithOutbox } from "./sync/SubmissionCoordinator";
import type { FormFieldDef } from "./types";

/**
 * Dedicated mobile page for TEAM_SHEET_PIECE_MEASUREMENT (班组配片记录).
 * Team-lead batch mode: select worker → fill form → submit on worker's behalf.
 */
export function MobileTeamSheetPiecePage() {
  const navigate = useNavigate();
  const { sessionMetadata } = useMobileSession();
  const [fields, setFields] = useState<FormFieldDef[]>([]);
  const [initialValues, setInitialValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [formTitle, setFormTitle] = useState("班组配片记录");
  const [definitionVersionId, setDefinitionVersionId] = useState("");
  const [localDraftId] = useState(() => crypto.randomUUID());
  const [selectedWorker, setSelectedWorker] = useState("");
  const [teamWorkers, setTeamWorkers] = useState<
    { employee_code: string; employee_name: string }[]
  >([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [schema, ctx, memberData] = await Promise.all([
          mobileApiClient.getFormSchema("TEAM_SHEET_PIECE_MEASUREMENT"),
          mobileApiClient.getProductionContext(),
          mobileApiClient.getTeamMembers(),
        ]);
        if (cancelled) return;
        setFields(schema.fields);
        setFormTitle(schema.title);
        setDefinitionVersionId(schema.definition_version_id);
        setInitialValues({
          occurred_date: ctx.date,
          shift: ctx.shift,
          work_order_id: ctx.work_orders?.[0] ?? "",
          material_spec: ctx.specs?.[0] ?? ctx.products?.[0] ?? "",
          pieces_per_block: ctx.pieces_per_block ?? "",
          block_count: "",
        });
        setTeamWorkers(memberData.members);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const handleSubmit = useCallback(
    async (values: Record<string, unknown>) => {
      if (!selectedWorker) {
        setError("请选择工人");
        return;
      }
      setSubmitting(true);
      setError("");
      try {
        if (!sessionMetadata) throw new Error("登录状态已失效，请重新登录。");
        const editableValues = Object.fromEntries(
          fields
            .filter((field) => field.editable && field.field_name in values)
            .map((field) => [field.field_name, values[field.field_name]]),
        );
        const result = await submitWithOutbox({
          form_type: "TEAM_SHEET_PIECE_MEASUREMENT",
          definition_version_id: definitionVersionId,
          mode: "TEAM_LEADER_BATCH",
          subject_employee_code: selectedWorker,
          device_id: getMobileDeviceId(),
          values: editableValues,
        }, crypto.randomUUID(), {
          owner: sessionMetadata.employee_code,
          deviceId: getMobileDeviceId(),
          localDraftId,
        });
        navigate(result ? "/mobile/submissions" : "/mobile/outbox", { replace: true });
      } catch (err) {
        setError(err instanceof Error ? err.message : "提交失败");
      } finally {
        setSubmitting(false);
      }
    },
    [definitionVersionId, fields, localDraftId, navigate, selectedWorker, sessionMetadata],
  );

  const handleSaveDraft = useCallback(
    async (values: Record<string, unknown>) => {
      setSubmitting(true);
      setError("");
      try {
        if (!sessionMetadata) throw new Error("登录状态已失效，请重新登录。");
        await saveDraft({
          localDraftId,
          owner: sessionMetadata.employee_code,
          deviceId: getMobileDeviceId(),
          formType: "TEAM_SHEET_PIECE_MEASUREMENT",
          definitionVersionId,
          values: { ...values, subject_employee_code: selectedWorker },
          updatedAt: new Date().toISOString(),
        });
        navigate("/mobile/drafts", { replace: true });
      } catch (err) {
        setError(err instanceof Error ? err.message : "保存草稿失败");
      } finally {
        setSubmitting(false);
      }
    },
    [definitionVersionId, localDraftId, navigate, selectedWorker, sessionMetadata],
  );

  if (loading) {
    return (
      <div className="mobile-page">
        <div className="mobile-loading">加载中…</div>
      </div>
    );
  }

  return (
    <div className="mobile-page">
      <header className="mobile-page-header">
        <Link to="/mobile/record" className="text-button">
          ← 返回
        </Link>
        <h2>{formTitle}</h2>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <MobileFormEngine
        fields={fields}
        initialValues={initialValues}
        onSubmit={handleSubmit}
        submitting={submitting}
        submitLabel={`为${selectedWorker ? teamWorkers.find((w) => w.employee_code === selectedWorker)?.employee_name ?? "—" : "—"}提交`}
        onSaveDraft={handleSaveDraft}
        draftLabel="保存草稿"
      >
        {/* Worker selector */}
        <div className="mobile-worker-select">
          <label htmlFor="team-worker-pick">选择工人</label>
          <select
            id="team-worker-pick"
            value={selectedWorker}
            onChange={(e) => setSelectedWorker(e.target.value)}
          >
            <option value="">-- 请选择 --</option>
            {teamWorkers.map((w) => (
              <option key={w.employee_code} value={w.employee_code}>
                {w.employee_name} ({w.employee_code})
              </option>
            ))}
          </select>
        </div>
      </MobileFormEngine>

      <div className="mobile-form-footer-note">
        <small>班组配片记录：班组长代为填写，总片数自动计算</small>
      </div>
    </div>
  );
}
