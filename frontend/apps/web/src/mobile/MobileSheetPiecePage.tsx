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
 * Dedicated mobile page for SHEET_PIECE_MEASUREMENT (配片工作记录).
 * Single-step form: loads schema + production context, renders via MobileFormEngine.
 */
export function MobileSheetPiecePage() {
  const navigate = useNavigate();
  const { sessionMetadata } = useMobileSession();
  const [fields, setFields] = useState<FormFieldDef[]>([]);
  const [initialValues, setInitialValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [formTitle, setFormTitle] = useState("配片工作记录");
  const [definitionVersionId, setDefinitionVersionId] = useState("");
  const [localDraftId] = useState(() => crypto.randomUUID());

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [schema, ctx] = await Promise.all([
          mobileApiClient.getFormSchema("SHEET_PIECE_MEASUREMENT"),
          mobileApiClient.getProductionContext(),
        ]);
        if (cancelled) return;
        setFields(schema.fields);
        setFormTitle(schema.title);
        setDefinitionVersionId(schema.definition_version_id);
        // Build initial values from production context
        setInitialValues({
          occurred_date: ctx.date,
          shift: ctx.shift,
          work_order_id: ctx.work_orders?.[0] ?? "",
          material_spec: ctx.specs?.[0] ?? ctx.products?.[0] ?? "",
          pieces_per_block: ctx.pieces_per_block ?? "",
          block_count: "",
        });
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
          form_type: "SHEET_PIECE_MEASUREMENT",
          definition_version_id: definitionVersionId,
          mode: "SELF",
          subject_employee_code: sessionMetadata.employee_code,
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
    [definitionVersionId, fields, localDraftId, navigate, sessionMetadata],
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
          formType: "SHEET_PIECE_MEASUREMENT",
          definitionVersionId,
          values,
          updatedAt: new Date().toISOString(),
        });
        navigate("/mobile/drafts", { replace: true });
      } catch (err) {
        setError(err instanceof Error ? err.message : "保存草稿失败");
      } finally {
        setSubmitting(false);
      }
    },
    [definitionVersionId, localDraftId, navigate, sessionMetadata],
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
        submitLabel="提交"
        onSaveDraft={handleSaveDraft}
        draftLabel="保存草稿"
      />

      <div className="mobile-form-footer-note">
        <small>总片数 = 每块片数 × 完成块数，系统自动计算</small>
      </div>
    </div>
  );
}
