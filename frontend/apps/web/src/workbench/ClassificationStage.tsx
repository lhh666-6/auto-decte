import { useEffect, useState } from "react";

import type { ClassificationOption, TaskStatusDetail } from "@form-detection/api-client";

import { RecognitionProgress, type TaskStatusReader } from "./RecognitionProgress";

interface AssignmentResult {
  recognition_task_id: string;
}

interface ClassificationStageProps {
  formId: string;
  options: ClassificationOption[];
  assignTemplate(input: {
    templateKey: string;
    version: number;
    reason: string;
  }): Promise<AssignmentResult>;
  taskApi: TaskStatusReader;
  onRecognitionSucceeded(task: TaskStatusDetail): void | Promise<void>;
  onError(message: string): void;
}

export function ClassificationStage({
  formId,
  options,
  assignTemplate,
  taskApi,
  onRecognitionSucceeded,
  onError,
}: ClassificationStageProps) {
  const [selectedValue, setSelectedValue] = useState("");
  const [reason, setReason] = useState("");
  const [taskId, setTaskId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setSelectedValue("");
    setReason("");
    setTaskId("");
    setSubmitting(false);
  }, [formId]);

  const selected = options.find(
    (option) => `${option.template_key}@${option.version}` === selectedValue,
  );

  async function submit() {
    if (!selected || !reason.trim()) {
      return;
    }

    setSubmitting(true);
    try {
      const assignment = await assignTemplate({
        templateKey: selected.template_key,
        version: selected.version,
        reason: reason.trim(),
      });
      setTaskId(assignment.recognition_task_id);
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "表单分类提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="classification-card">
      <h2>二维码未能确定表单类型</h2>
      <p>请选择准确的已发布版本，并说明判断依据后开始识别。</p>

      <label>
        已发布模板版本
        <select
          value={selectedValue}
          onChange={(event) => setSelectedValue(event.target.value)}
          disabled={Boolean(taskId)}
        >
          <option value="">请选择模板版本</option>
          {options.map((option) => (
            <option
              key={`${option.template_key}@${option.version}`}
              value={`${option.template_key}@${option.version}`}
            >
              {option.template_key} · V{option.version}
            </option>
          ))}
        </select>
      </label>

      <label>
        分类原因
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          disabled={Boolean(taskId)}
          placeholder="例如：版式、标题和字段位置与该版本一致"
        />
      </label>

      <div aria-label="模板摘要">
        <strong>模板摘要</strong>
        {selected ? (
          <p>
            {selected.template_key} · V{selected.version} · {selected.field_count} 个字段 · {selected.page_size} {selected.orientation}
          </p>
        ) : (
          <ul>
            {options.map((option) => (
              <li key={`${option.template_key}-summary-${option.version}`}>
                {option.template_key} · V{option.version} · {option.field_count} 个字段 · {option.page_size} {option.orientation}
              </li>
            ))}
          </ul>
        )}
      </div>

      {!taskId ? (
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!selected || !reason.trim() || submitting}
        >
          {submitting ? "正在创建识别任务" : "确认表单类型并开始识别"}
        </button>
      ) : (
        <RecognitionProgress
          taskId={taskId}
          taskApi={taskApi}
          onSucceeded={onRecognitionSucceeded}
          onFailure={(task) => onError(task.error || `识别任务${task.status}`)}
        />
      )}
    </section>
  );
}
