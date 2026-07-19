import type { EvidenceItem, RecognitionCandidate, ReviewField, ReviewHistory } from "@form-detection/api-client";

import { fieldBehaviorSummary, fieldUsesAutomaticRecognition } from "./field-behavior";

interface FieldDetailPanelProps {
  selectedField: ReviewField | null;
  evidence: readonly EvidenceItem[];
  history: ReviewHistory | null;
  warningCount: number;
  ruleFailure: string | null;
  onUseCandidate: (fieldId: string, candidate: RecognitionCandidate) => void;
}

export function FieldDetailPanel({
  selectedField,
  evidence,
  history,
  warningCount,
  ruleFailure,
  onUseCandidate,
}: FieldDetailPanelProps) {
  const crop = evidence.find((item) => (
    item.type === "FIELD_CROP" && item.related_field_id === selectedField?.field_id
  ));
  const automaticRecognition = selectedField
    ? fieldUsesAutomaticRecognition(selectedField)
    : false;
  return (
    <section className="detail-drawer field-detail-panel">
      <div className="drawer-heading">
        <div>
          <span className="eyebrow">字段详情</span>
          <strong>{selectedField ? selectedField.display_name ?? selectedField.field_name : "选择一个字段查看详情"}</strong>
        </div>
        <span className={warningCount > 0 ? "status-pill warning" : "status-pill success"}>
          {selectedField?.requires_manual_confirmation
            ? "必须人工确认"
            : warningCount > 0 ? `${warningCount} 项待确认` : "无待确认项"}
        </span>
      </div>
      <div className="drawer-columns">
        <div>
          <span className="drawer-label">原图裁片</span>
          {crop ? (
            <img className="field-detail-crop" src={crop.download_url} alt="原图裁片" />
          ) : (
            <span className={selectedField?.requires_manual_confirmation ? "inline-warning" : "muted"}>
              {selectedField?.requires_manual_confirmation
                ? "缺少裁片，不能完成人工确认"
                : "该字段没有可用裁片"}
            </span>
          )}
        </div>
        <div>
          <span className="drawer-label">填写与识别</span>
          {selectedField && <span className="muted">{fieldBehaviorSummary(selectedField)}</span>}
          {automaticRecognition && selectedField?.candidates.length ? selectedField.candidates.map((candidate) => (
            <button key={candidate.attempt_id} type="button" className="candidate-chip" onClick={() => onUseCandidate(selectedField.field_id, candidate)}>
              {String(candidate.candidate_value ?? "")} <span>{Math.round(candidate.confidence * 100)}%</span>
            </button>
          )) : (
            <span className="muted">
              {automaticRecognition ? "暂无识别候选" : "该字段不产生识别候选或可靠度"}
            </span>
          )}
        </div>
        <div>
          <span className="drawer-label">填报规则与错误</span>
          {ruleFailure && <span className="inline-warning">{ruleFailure}</span>}
          {selectedField?.rules ? (
            <span className="muted">
              {selectedField.rules.required ? "必填" : "选填"}
              {selectedField.rules.minimum_value !== null ? ` · 最小值 ${selectedField.rules.minimum_value}` : ""}
              {selectedField.rules.maximum_value !== null ? ` · 最大值 ${selectedField.rules.maximum_value}` : ""}
              {selectedField.rules.allowed_values.length ? ` · 允许值：${selectedField.rules.allowed_values.join("、")}` : ""}
              {selectedField.rules.master_data_options.length ? ` · 主数据选项 ${selectedField.rules.master_data_options.length} 项` : ""}
            </span>
          ) : <span className="muted">没有额外填报规则</span>}
        </div>
        <div>
          <span className="drawer-label">历史与证据</span>
          <span className="muted">{history?.versions.length ?? 0} 个版本 · {history?.audits.length ?? 0} 条审计事件 · {evidence.length} 个受控文件</span>
        </div>
      </div>
    </section>
  );
}
