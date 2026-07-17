import type { EvidenceItem, RecognitionCandidate, ReviewField, ReviewHistory } from "@form-detection/api-client";

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
  return (
    <section className="detail-drawer field-detail-panel">
      <div className="drawer-heading">
        <div>
          <span className="eyebrow">字段详情</span>
          <strong>{selectedField ? selectedField.display_name ?? selectedField.field_name : "选择一个字段查看详情"}</strong>
        </div>
        <span className={warningCount > 0 ? "status-pill warning" : "status-pill success"}>
          {warningCount > 0 ? `${warningCount} 项待确认` : "无待确认项"}
        </span>
      </div>
      <div className="drawer-columns">
        <div>
          <span className="drawer-label">字段裁片</span>
          {crop ? <img className="field-detail-crop" src={crop.download_url} alt="字段裁片" /> : <span className="muted">该字段没有可用裁片</span>}
        </div>
        <div>
          <span className="drawer-label">识别候选</span>
          {selectedField?.candidates.length ? selectedField.candidates.map((candidate) => (
            <button key={candidate.attempt_id} type="button" className="candidate-chip" onClick={() => onUseCandidate(selectedField.field_id, candidate)}>
              {String(candidate.candidate_value ?? "")} <span>{Math.round(candidate.confidence * 100)}%</span>
            </button>
          )) : <span className="muted">{selectedField?.recognition_engine === "manual" ? "该字段配置为人工录入" : "暂无 OCR/OMR 候选"}</span>}
        </div>
        <div>
          <span className="drawer-label">填报规则与错误</span>
          {ruleFailure && <span className="inline-warning">{ruleFailure}</span>}
          {selectedField?.rules ? (
            <span className="muted">
              {selectedField.rules.required ? "必填" : "选填"}
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
