import type { QueueKey } from "./workbench-types";

interface WorkbenchEmptyStateProps {
  queue: Exclude<QueueKey, "exportable">;
  onUpload(): void;
  onFind(): void;
}

const EMPTY_COPY = {
  classification: {
    heading: "没有待确认类型的表单",
    body: "上传二维码无法识别的表单照片后，可在这里选择准确的已发布模板。",
  },
  review: {
    heading: "没有待审核的表单",
    body: "当前审核队列已经处理完毕，可以上传新照片或按编号查找已有表单。",
  },
  exceptions: {
    heading: "没有待重新拍照的表单",
    body: "当前没有因照片质量或业务规则而需要重新采集的表单。",
  },
} as const;

export function WorkbenchEmptyState({ queue, onUpload, onFind }: WorkbenchEmptyStateProps) {
  const copy = EMPTY_COPY[queue];
  return (
    <section className="workbench-empty-state">
      <span className="eyebrow">当前队列为空</span>
      <h2>{copy.heading}</h2>
      <p>{copy.body}</p>
      <div>
        <button type="button" className="button button-primary" onClick={onUpload}>
          上传表单照片
        </button>
        <button type="button" className="button button-secondary" onClick={onFind}>
          查找表单
        </button>
      </div>
    </section>
  );
}

export function WorkbenchErrorNotice({ error }: { error: string }) {
  const match = /^([A-Z][A-Z0-9_]+)：(.+)$/.exec(error);
  const code = match?.[1] ?? null;
  const message = match?.[2] ?? error;

  return (
    <section className="error-banner workbench-error" role="alert">
      <div>
        <strong>操作没有完成</strong>
        <p>{message}，当前步骤不能继续。</p>
        <p>请刷新状态后重试；若仍失败，请检查输入与网络连接。</p>
        {code ? (
          <details>
            <summary>追溯详情</summary>
            <code>{code}</code>
          </details>
        ) : null}
      </div>
    </section>
  );
}
