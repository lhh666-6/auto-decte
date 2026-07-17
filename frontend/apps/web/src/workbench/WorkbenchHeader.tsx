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
        <span>{detail ? `模板 ${detail.form.template_id} · v${detail.form.template_version}` : "输入编号后加载"}</span>
        {detail && (
          <span>
            记录版本 {detail.form.current_record_version} · {reviewStatus?.label} · {exportStatus?.label}
          </span>
        )}
        {detail && (
          <TraceDetails items={[
            { label: "审核状态代码", value: reviewStatus?.technicalLabel ?? "" },
            { label: "导出状态代码", value: exportStatus?.technicalLabel ?? "" },
          ]} />
        )}
      </div>
      <div className="lease-summary">
        {lease
          ? <span className="lease-active">审核锁有效至 {new Date(lease.expires_at).toLocaleTimeString()}</span>
          : <span>未获取审核锁</span>}
        {lease ? (
          <button type="button" className="text-button" onClick={onReleaseLease}>释放</button>
        ) : (
          <button type="button" className="text-button" disabled={!detail} onClick={onAcquireLease}>获取审核锁</button>
        )}
      </div>
    </section>
  );
}
