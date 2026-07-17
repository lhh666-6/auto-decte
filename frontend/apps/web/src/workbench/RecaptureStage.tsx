import type { ReviewHistory, WorkbenchDetail } from "@form-detection/api-client";

interface RecaptureStageProps {
  detail: WorkbenchDetail;
  history: ReviewHistory | null;
  onUpload(file: File): void;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未识别";
  return typeof value === "string" ? value : JSON.stringify(value);
}

export function RecaptureStage({ detail, history, onUpload }: RecaptureStageProps) {
  const image = detail.evidence.find((item) => item.type === "CORRECTED_IMAGE")
    ?? detail.evidence.find((item) => item.type === "ORIGINAL_IMAGE")
    ?? detail.evidence[0];
  const returnedAudit = [...(history?.audits ?? [])]
    .reverse()
    .find((audit) => audit.reason && audit.event_type.toUpperCase().includes("RETURN"));
  const lastValues = detail.current_record?.values ?? {};

  return (
    <section className="recapture-stage">
      <div className="review-grid" data-testid="recapture-workbench-grid">
        <section className="evidence-panel">
          <div className="panel-toolbar">
            <strong>上次照片</strong>
            <span>只读证据</span>
          </div>
          <div className="canvas-stage">
            {image ? (
              <img src={image.download_url} alt="上次拍摄的表单" />
            ) : (
              <p className="empty-canvas">上次照片当前不可用</p>
            )}
          </div>
        </section>

        <section className="field-panel">
          <div className="panel-toolbar">
            <strong>待重新拍照</strong>
            <span>{detail.form.form_id}</span>
          </div>
          <div className="detail-drawer">
            <h2>退回原因</h2>
            <p>{returnedAudit?.reason ?? "审核记录中没有可用的退回原因，请查看历史记录。"}</p>

            <h3>上次结果</h3>
            {Object.keys(lastValues).length > 0 ? (
              <ul>
                {Object.entries(lastValues).map(([key, value]) => (
                  <li key={key}>{key}：{displayValue(value)}</li>
                ))}
              </ul>
            ) : <p>上次没有形成可用结果。</p>}

            <h3>异常字段</h3>
            <ul>
              {detail.fields.map((field) => (
                <li key={field.field_id}>
                  {field.display_name ?? field.field_name}：{displayValue(field.current_value)}
                </li>
              ))}
            </ul>

            <details>
              <summary>历史记录</summary>
              <ul>
                {(history?.audits ?? []).map((audit) => (
                  <li key={audit.event_id}>
                    {new Date(audit.timestamp).toLocaleString()} · {audit.reason ?? audit.event_type}
                  </li>
                ))}
              </ul>
            </details>
          </div>
        </section>
      </div>

      <section className="detail-drawer">
        <h2>上传新的表单照片</h2>
        <p>
          上传后会创建一张新表单；当前版本尚不能自动关联为原表单的替换证据。
          原表单与新照片的永久追溯，需要后端替换证据接口完成后才能闭环。
        </p>
        <label className="button button-primary">
          上传新的表单照片
          <input
            className="visually-hidden"
            type="file"
            accept="image/png,image/jpeg,image/tiff"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload(file);
              event.target.value = "";
            }}
          />
        </label>
      </section>
    </section>
  );
}
