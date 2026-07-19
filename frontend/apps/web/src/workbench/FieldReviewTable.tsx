import { Fragment } from "react";

import type { ReviewField } from "@form-detection/api-client";

import { reviewValueIssue } from "../review-model";
import {
  fieldReviewGroup,
  fieldUsesAutomaticRecognition,
  REVIEW_GROUPS,
  workerNumberIssue,
  workerNumberMatch,
} from "./field-behavior";

interface FieldReviewTableProps {
  fields: readonly ReviewField[];
  edits: Readonly<Record<string, unknown>>;
  recordValues: Readonly<Record<string, unknown>>;
  ruleFailures: Readonly<Record<string, string>>;
  selectedFieldId: string | null;
  hoveredFieldId: string | null;
  onSelectField: (fieldId: string) => void;
  onHoverField: (fieldId: string | null) => void;
  onEdit: (fieldId: string, value: string) => void;
}

export function FieldReviewTable({
  fields,
  edits,
  recordValues,
  ruleFailures,
  selectedFieldId,
  hoveredFieldId,
  onSelectField,
  onHoverField,
  onEdit,
}: FieldReviewTableProps) {
  const orderedFields = REVIEW_GROUPS.flatMap(({ key }) => (
    fields.filter((field) => fieldReviewGroup(field) === key)
  ));
  return (
    <section className="field-panel" aria-label="可编辑电子表格">
      <div className="panel-toolbar"><strong>电子表格</strong><span>{fields.length} 个字段</span></div>
      <div className="field-table" role="table">
        <div className="field-row field-head" role="row">
          <span>字段</span><span>系统识别值</span><span>识别可靠度</span><span>最终填写值</span><span>文字状态</span>
        </div>
        {fields.length === 0 ? <div className="table-empty">尚未加载字段</div> : orderedFields.map((field, index) => {
          const group = fieldReviewGroup(field);
          const showGroupHeading = index === 0 || fieldReviewGroup(orderedFields[index - 1]) !== group;
          const automaticRecognition = fieldUsesAutomaticRecognition(field);
          const candidate = automaticRecognition ? field.candidates[0] : undefined;
          const displayValue = valueForField(field, edits, recordValues);
          const manuallyEdited = Object.hasOwn(edits, field.field_id) || Object.hasOwn(edits, field.field_name);
          const manuallyConfirmed = manuallyEdited || field.current_value_source === "HUMAN_CONFIRMED";
          const issue = ruleFailures[field.field_id] ?? ruleFailures[field.field_name] ?? workerNumberIssue(
            field,
            displayValue,
          ) ?? reviewValueIssue(
            displayValue,
            candidate?.confidence,
            manuallyConfirmed,
            field.data_type,
            field.rules,
            field.requires_manual_confirmation,
          );
          const workerMatch = workerNumberMatch(field, displayValue);
          const label = field.display_name ?? field.field_name;
          return (
            <Fragment key={field.field_id}>
              {showGroupHeading ? (
                <div className="field-group-heading">
                  {REVIEW_GROUPS.find((item) => item.key === group)?.label ?? group}
                </div>
              ) : null}
              <div
              id={`review-field-row-${field.field_id}`}
              className={[
                "field-row",
                field.field_id === selectedFieldId ? "selected" : "",
                field.field_id === hoveredFieldId ? "hovered" : "",
                issue ? "has-warning" : "",
              ].filter(Boolean).join(" ")}
              role="row"
              tabIndex={0}
              onClick={() => onSelectField(field.field_id)}
              onMouseEnter={() => onHoverField(field.field_id)}
              onMouseLeave={() => onHoverField(null)}
              onFocus={() => onHoverField(field.field_id)}
              onBlur={() => onHoverField(null)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") onSelectField(field.field_id);
              }}
            >
              <span className="field-name"><strong>{label}</strong>{field.display_name && <small>{field.field_name}</small>}</span>
              <span className="candidate-value">{candidate ? stringValue(candidate.candidate_value) : "—"}</span>
              <span>{candidate ? `${Math.round(candidate.confidence * 100)}%` : "—"}</span>
              <label className="final-value-control" onClick={(event) => event.stopPropagation()}>
                <span className="visually-hidden">{label} 确认值</span>
                {field.rules && (field.rules.master_data_options.length || field.rules.allowed_values.length) ? (
                  <select
                    id={`review-final-${field.field_id}`}
                    aria-label={`${label} 最终填写值`}
                    value={stringValue(displayValue)}
                    onChange={(event) => onEdit(field.field_id, event.target.value)}
                  >
                    <option value="">请选择</option>
                    {field.rules.master_data_options.length
                      ? field.rules.master_data_options.map((option) => <option key={option.value} value={option.value}>{option.label}（{option.value}）</option>)
                      : field.rules.allowed_values.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                ) : (
                  <input
                    id={`review-final-${field.field_id}`}
                    aria-label={`${label} 最终填写值`}
                    value={stringValue(displayValue)}
                    onChange={(event) => onEdit(field.field_id, event.target.value)}
                  />
                )}
              </label>
              <span>{issue ? (
                <>
                  <em className="inline-warning">待确认</em>
                  <small className="field-rule-message">{issue}</small>
                  {field.requires_manual_confirmation && !manuallyConfirmed &&
                  stringValue(displayValue).trim() ? (
                    <button
                      type="button"
                      className="field-confirm-button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onEdit(field.field_id, stringValue(displayValue));
                      }}
                    >确认姓名与原图一致</button>
                  ) : null}
                </>
              ) : (
                <em className="inline-success">
                  {workerMatch === "MATCHED" ? "工号已匹配" : "已就绪"}
                </em>
              )}</span>
              </div>
            </Fragment>
          );
        })}
      </div>
    </section>
  );
}

function stringValue(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function valueForField(
  field: ReviewField,
  edits: Readonly<Record<string, unknown>>,
  recordValues: Readonly<Record<string, unknown>>,
): unknown {
  if (Object.hasOwn(edits, field.field_id)) return edits[field.field_id];
  if (Object.hasOwn(edits, field.field_name)) return edits[field.field_name];
  if (Object.hasOwn(recordValues, field.field_id)) return recordValues[field.field_id];
  if (Object.hasOwn(recordValues, field.field_name)) return recordValues[field.field_name];
  return field.current_value;
}
