import type { FormFieldDef } from "../types";
import { computePreview } from "./computation";
import { isFieldVisible } from "./validation";
import { classifyStrategy, type ComputeMap, type ConditionalMap } from "./types";

interface FieldRendererProps {
  field: FormFieldDef;
  values: Record<string, unknown>;
  errors: Record<string, string>;
  touched: Record<string, boolean>;
  conditionals: ConditionalMap;
  computations: ComputeMap;
  setValue: (field: string, value: unknown) => void;
}

function fieldLabel(field: FormFieldDef): string {
  return field.required && field.strategy !== "AUTO_READ_ONLY" ? `${field.label} *` : field.label;
}

function ErrorMessage({ field, error, show }: { field: string; error?: string; show: boolean }) {
  return show ? <span id={`${field}-error`} className="mobile-field-error">{error}</span> : null;
}

function inputAccessibility(field: FormFieldDef, showError: boolean) {
  return {
    id: `mobile-field-${field.field_name}`,
    "aria-invalid": showError || undefined,
    "aria-describedby": showError ? `${field.field_name}-error` : undefined,
  };
}

export function FieldRenderer({
  field,
  values,
  errors,
  touched,
  conditionals,
  computations,
  setValue,
}: FieldRendererProps) {
  const strategy = classifyStrategy(field.strategy);
  const value = values[field.field_name] ?? field.default_value ?? "";
  const error = errors[field.field_name];
  const showError = Boolean(touched[field.field_name] && error);

  if (!isFieldVisible(field, values, conditionals)) return null;
  if (strategy === "computed") {
    return (
      <div className="mobile-computed-value">
        <span>{field.label}</span>
        <strong>{computePreview(field.field_name, values, computations)}</strong>
      </div>
    );
  }
  if (strategy === "choice") {
    const labels: Record<string, string> = { NORMAL: "正常", EXCEPTION: "异常", 正常: "正常", 异常: "异常" };
    return (
      <fieldset className="mobile-preset-group">
        <legend>{fieldLabel(field)}</legend>
        <div className="mobile-preset-buttons">
          {(field.preset_options ?? []).map((option) => (
            <button
              key={option}
              type="button"
              className={`mobile-preset-button${value === option ? " active" : ""}`}
              onClick={() => setValue(field.field_name, option)}
            >
              {labels[option] ?? option}
            </button>
          ))}
        </div>
        <ErrorMessage field={field.field_name} error={error} show={showError} />
      </fieldset>
    );
  }
  if (strategy === "conditional") {
    if (field.preset_options?.length) {
      return (
        <fieldset className="mobile-preset-group">
          <legend>{fieldLabel(field)}</legend>
          <div className="mobile-preset-chips">
            {field.preset_options.map((option) => (
              <button
                key={option}
                type="button"
                className={`mobile-preset-chip${value === option ? " active" : ""}`}
                onClick={() => setValue(field.field_name, value === option ? "" : option)}
              >
                {option}
              </button>
            ))}
          </div>
          <ErrorMessage field={field.field_name} error={error} show={showError} />
        </fieldset>
      );
    }
    return (
      <label>
        <span>{fieldLabel(field)}</span>
        <textarea
          {...inputAccessibility(field, showError)}
          rows={3}
          value={String(value)}
          onChange={(event) => setValue(field.field_name, event.target.value)}
          placeholder="请描述异常情况（≤100字）"
          maxLength={100}
        />
        <ErrorMessage field={field.field_name} error={error} show={showError} />
      </label>
    );
  }
  if (strategy === "required") {
    return (
      <label className="mobile-field-required">
        <span>{fieldLabel(field)}</span>
        <input
          {...inputAccessibility(field, showError)}
          type="number"
          inputMode="decimal"
          value={value === "" || value === null || value === undefined ? "" : String(value)}
          onChange={(event) => setValue(field.field_name, event.target.value === "" ? "" : Number(event.target.value))}
          required
        />
        <ErrorMessage field={field.field_name} error={error} show={showError} />
      </label>
    );
  }
  if (strategy !== "editable") return null;

  if (field.field_name === "occurred_date" || field.field_name.endsWith("_date")) {
    return (
      <label>
        <span>{fieldLabel(field)}</span>
        <input
          {...inputAccessibility(field, showError)}
          type="date"
          value={String(value)}
          onChange={(event) => setValue(field.field_name, event.target.value)}
        />
        <ErrorMessage field={field.field_name} error={error} show={showError} />
      </label>
    );
  }
  if (field.preset_options?.length) {
    return (
      <label>
        <span>{fieldLabel(field)}</span>
        <select
          {...inputAccessibility(field, showError)}
          value={String(value || field.preset_options[0])}
          onChange={(event) => setValue(field.field_name, event.target.value)}
        >
          {field.preset_options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
        <ErrorMessage field={field.field_name} error={error} show={showError} />
      </label>
    );
  }
  const isNumber = field.input_type === "number";
  return (
    <label>
      <span>{fieldLabel(field)}</span>
      <input
        {...inputAccessibility(field, showError)}
        type={isNumber ? "number" : "text"}
        inputMode={isNumber ? "decimal" : "text"}
        value={isNumber && (value === "" || value === null || value === undefined) ? "" : String(value ?? "")}
        onChange={(event) => setValue(
          field.field_name,
          isNumber ? (event.target.value === "" ? "" : Number(event.target.value)) : event.target.value,
        )}
        placeholder={field.field_name === "work_order_id" ? "如：WO-2026-001" : undefined}
      />
      <ErrorMessage field={field.field_name} error={error} show={showError} />
    </label>
  );
}
