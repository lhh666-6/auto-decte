import { useCallback, useMemo, useReducer } from "react";

import { buildComputeMap, buildSubmissionValues } from "./computation";
import { FieldRenderer } from "./FieldRenderer";
import { createFormState, formReducer } from "./reducer";
import { buildConditionalMap, validateForm } from "./validation";
import { classifyStrategy, type MobileFormEngineProps } from "./types";

export function MobileFormEngine({
  fields,
  initialValues = {},
  conditionalRules = [],
  computeRules = [],
  onSubmit,
  submitting = false,
  submitLabel = "提交",
  onSaveDraft,
  draftLabel = "保存草稿",
  children,
}: MobileFormEngineProps) {
  const [state, dispatch] = useReducer(formReducer, initialValues, createFormState);
  const conditionals = useMemo(() => buildConditionalMap(conditionalRules), [conditionalRules]);
  const computations = useMemo(() => buildComputeMap(computeRules), [computeRules]);

  const setValue = useCallback((field: string, value: unknown) => {
    const nextValues = { ...state.values, [field]: value };
    const clearFields = [...conditionals.values()]
      .filter((rule) => rule.dependsOn === field && !rule.showWhen(nextValues[field]))
      .map((rule) => rule.fieldName);
    dispatch({ type: "SET_VALUE", field, value, clearFields });
  }, [conditionals, state.values]);

  const handleSubmit = useCallback((event: React.FormEvent) => {
    event.preventDefault();
    const failures = validateForm(fields, state.values, conditionals);
    if (failures.length) {
      dispatch({
        type: "VALIDATION_FAILED",
        errors: Object.fromEntries(failures.map((failure) => [failure.field, failure.message])),
      });
      return;
    }
    onSubmit(buildSubmissionValues(fields, state.values, computations));
  }, [computations, conditionals, fields, onSubmit, state.values]);

  const readonlyFields = fields.filter((field) => classifyStrategy(field.strategy) === "readonly");
  const visibleFields = fields.filter((field) => {
    const strategy = classifyStrategy(field.strategy);
    return strategy !== "hidden" && strategy !== "readonly";
  });

  return (
    <form className="mobile-form-engine" onSubmit={handleSubmit} noValidate>
      {readonlyFields.length > 0 && (
        <div className="mobile-readonly-section">
          {readonlyFields.map((field) => (
            <div key={field.field_name} className="mobile-readonly-row">
              <span>{field.label}</span>
              <strong>{String(state.values[field.field_name] ?? field.default_value ?? "—")}</strong>
            </div>
          ))}
        </div>
      )}

      {children}

      {visibleFields.map((field) => (
        <FieldRenderer
          key={field.field_name}
          field={field}
          values={state.values}
          errors={state.errors}
          touched={state.touched}
          conditionals={conditionals}
          computations={computations}
          setValue={setValue}
        />
      ))}

      <div className="mobile-form-actions">
        {onSaveDraft && (
          <button
            type="button"
            className="button button-secondary"
            disabled={submitting}
            onClick={() => onSaveDraft(state.values)}
          >
            {draftLabel}
          </button>
        )}
        <button type="submit" className="button button-primary" disabled={submitting}>
          {submitting ? "提交中…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
