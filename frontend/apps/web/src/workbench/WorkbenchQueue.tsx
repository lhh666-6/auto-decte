import type { FormSummary } from "@form-detection/api-client";

import { getReviewStatusCopy } from "../ui/business-language";
import type { QueueKey } from "./workbench-types";

const QUEUE_LABELS: Record<QueueKey, string> = {
  classification: "待确认表单类型",
  review: "待核对",
  exceptions: "待重新拍照",
};

interface WorkbenchQueueProps {
  selectedQueue: QueueKey;
  forms: readonly FormSummary[];
  onOpenForm: (formId: string) => void;
}

export function WorkbenchQueue({ selectedQueue, forms, onOpenForm }: WorkbenchQueueProps) {
  if (forms.length === 0) return null;

  return (
    <section className="queue-panel" aria-label="当前审核队列">
      <div>
        <span className="eyebrow">当前队列</span>
        <strong>{QUEUE_LABELS[selectedQueue]}</strong>
        {selectedQueue === "review" && <span className="visually-hidden">待复核</span>}
      </div>
      <div className="queue-form-list">
        {forms.map((form) => {
          const status = getReviewStatusCopy(form.review_status);
          return (
            <button key={form.form_id} type="button" onClick={() => onOpenForm(form.form_id)}>
              <strong>{form.form_id}</strong>
              <span>{form.template_id} · {status.label} · 优先级 {form.priority}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
