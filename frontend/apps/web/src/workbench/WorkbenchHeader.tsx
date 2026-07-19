import type { ReviewLease, WorkbenchDetail } from "@form-detection/api-client";

import { getExportStatusCopy, getReviewStatusCopy } from "../ui/business-language";
import { TraceDetails } from "../ui/TraceDetails";

interface WorkbenchHeaderProps {
  formIdInput: string;
  detail: WorkbenchDetail | null;
  lease: ReviewLease | null;
  loading: boolean;
  uploading: boolean;
  onFormIdInputChange: (value: string) => void;
  onLoad: () => void;
  onImportImage: (file: File | null) => void;
  onAcquireLease: () => void;
  onReleaseLease: () => void;
}

export function WorkbenchHeader({
  formIdInput,
  detail,
  lease,
  loading,
  uploading,
  onFormIdInputChange,
  onLoad,
  onImportImage,
  onAcquireLease,
  onReleaseLease,
}: WorkbenchHeaderProps) {
  const reviewStatus = detail ? getReviewStatusCopy(detail.form.review_status) : null;
  const exportStatus = detail ? getExportStatusCopy(detail.form.export_status) : null;
  return (
    <section className="context-card workbench-header">
      <form
        className="form-loader"
        onSubmit={(event) => {
          event.preventDefault();
          onLoad();
        }}
      >
        <label htmlFor="form-id">表单编号</label>
        <input
          id="form-id"
          value={formIdInput}
          onChange={(event) => onFormIdInputChange(event.target.value)}
          placeholder="例如 FORM-1"
        />
        <button type="submit" className="button button-secondary" disabled={loading}>加载表单</button>
        <label className="button button-primary import-image-button">
          {uploading ? "正在导入…" : "导入图片"}
          <input
            id="image-import"
            type="file"
            accept="image/png,image/jpeg,image/tiff"
            disabled={uploading}
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              event.target.value = "";
              onImportImage(file);
            }}
          />
        </label>
      </form>
      <div className="form-summary">
        <strong>{detail?.form.form_id ?? "未加载表单"}</strong>
        <span>{detail ? `已绑定模板 · V${detail.form.template_version}` : "输入编号后加载"}</span>
        {detail && (
          <span>
            记录版本 {detail.form.current_record_version} · {reviewStatus?.label} · {exportStatus?.label}
          </span>
        )}
        {detail && (
          <TraceDetails items={[
            { label: "模板编号", value: detail.form.template_id },
            { label: "模板版本", value: detail.form.template_version },
            { label: "审核状态代码", value: reviewStatus?.technicalLabel ?? "" },
            { label: "导出状态代码", value: exportStatus?.technicalLabel ?? "" },
          ]} />
        )}
      </div>
      <div className="lease-summary">
        {lease
          ? <span className="lease-active">你正在审核 · 有效至 {new Date(lease.expires_at).toLocaleTimeString()}</span>
          : <span>尚未开始审核</span>}
        {lease ? (
          <button type="button" className="text-button" onClick={onReleaseLease}>暂停审核</button>
        ) : (
          <button type="button" className="text-button" disabled={!detail} onClick={onAcquireLease}>开始审核</button>
        )}
      </div>
    </section>
  );
}
