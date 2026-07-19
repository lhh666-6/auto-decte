import { ImportApi, type ImportBatchSummary, type ImportedImageSummary } from "@form-detection/api-client";
import { useEffect, useState } from "react";

export function ImageOverview({ api, onOpenForm }: { api: ImportApi; onOpenForm: (formId: string) => void }) {
  const [images, setImages] = useState<ImportedImageSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { void api.listImages().then(setImages).catch((cause: unknown) => setError(message(cause))); }, [api]);
  if (error) return <div className="error-banner" role="alert">{error}</div>;
  return <section className="import-overview"><header><div><span className="eyebrow">缩略图视图</span><h2>图片总览</h2></div><span>{images.length} 张</span></header><div className="image-wall">{images.map((item) => <button type="button" key={item.form_id} className="image-card" onClick={() => onOpenForm(item.form_id)}><img src={item.thumbnail_url} alt={item.file_name} /><strong>{item.file_name}</strong><span>{reviewStatus(item.review_status)} · {item.template_id === "UNKNOWN" ? "待确认类型" : `模板 V${item.template_version}`}</span></button>)}</div>{images.length === 0 && <p className="muted">还没有导入图片。</p>}</section>;
}

export function ImportBatchOverview({ api }: { api: ImportApi }) {
  const [batches, setBatches] = useState<ImportBatchSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { void api.listBatches().then(setBatches).catch((cause: unknown) => setError(message(cause))); }, [api]);
  if (error) return <div className="error-banner" role="alert">{error}</div>;
  return <section className="import-overview"><header><div><span className="eyebrow">详细列表</span><h2>导入批次</h2></div><span>{batches.length} 批</span></header><div className="import-batch-list">{batches.map((batch) => <article key={batch.batch_id} className="import-batch-card"><div><strong>本次导入 {batch.counts.total} 张</strong><span>{new Date(batch.created_at).toLocaleString()}</span></div><p>成功 {batch.counts.succeeded}｜处理中 {batch.counts.processing}｜需要处理 {batch.counts.needs_action}｜失败 {batch.counts.failed}</p><details><summary>查看每张图片</summary>{batch.items.map((item) => <div className="batch-history-item" key={item.task_id}><span>{item.file_name}</span><span>{itemStatus(item.status)}</span></div>)}</details></article>)}</div>{batches.length === 0 && <p className="muted">还没有批量导入记录。</p>}</section>;
}

function reviewStatus(status: string) {
  return ({ NEEDS_CLASSIFICATION: "待确认类型", NEEDS_REVIEW: "待核对", RECAPTURE_REQUIRED: "待重新拍照", CONFIRMED: "已确认" } as Record<string, string>)[status] ?? "处理中";
}

function itemStatus(status: string) {
  return ({ SUCCEEDED: "已导入", PROCESSING: "处理中", NEEDS_ACTION: "需要处理", FAILED: "失败" } as Record<string, string>)[status] ?? status;
}

function message(cause: unknown) { return cause instanceof Error ? cause.message : "图片资料读取失败，请重试。"; }
