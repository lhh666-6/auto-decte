import { ImportApi, type ImportItemStatus } from "@form-detection/api-client";
import { useRef, useState } from "react";

type LocalItem = {
  id: string;
  file: File;
  status: ImportItemStatus;
  formId: string | null;
  detail: string | null;
};

type Props = {
  api: ImportApi;
  onClose: () => void;
  onChanged: () => void;
};

export function BatchImportPanel({ api, onClose, onChanged }: Props) {
  const [batchId, setBatchId] = useState<string | null>(null);
  const [items, setItems] = useState<LocalItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const running = useRef(false);

  function addFiles(files: File[]) {
    const accepted = files.filter((file) => ["image/png", "image/jpeg", "image/tiff"].includes(file.type));
    if (accepted.length === 0 || running.current) return;
    const nextBatch = `BATCH-${new Date().toISOString().replace(/\D/gu, "").slice(0, 14)}-${crypto.randomUUID().slice(0, 8)}`;
    const nextItems = accepted.map((file): LocalItem => ({
      id: crypto.randomUUID(), file, status: "QUEUED", formId: null, detail: null,
    }));
    setBatchId(nextBatch);
    setItems(nextItems);
    running.current = true;
    void runPool(nextItems, 3, (item) => upload(item, nextBatch)).finally(() => {
      running.current = false;
      onChanged();
    });
  }

  async function upload(item: LocalItem, targetBatch: string) {
    update(item.id, { status: "PROCESSING", detail: null });
    try {
      const result = await api.uploadImage(item.file, targetBatch, crypto.randomUUID());
      update(item.id, {
        status: result.status,
        formId: result.form_id,
        detail: result.status === "NEEDS_ACTION" ? result.detail : null,
      });
    } catch (cause) {
      update(item.id, {
        status: "FAILED",
        detail: cause instanceof Error ? cause.message : "导入失败，请重试。",
      });
    }
  }

  function update(id: string, patch: Partial<LocalItem>) {
    setItems((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item));
  }

  function retry(item: LocalItem) {
    if (!batchId || item.status === "PROCESSING") return;
    void upload(item, batchId).finally(onChanged);
  }

  const counts = countItems(items);
  return (
    <div className="dialog-backdrop batch-import-backdrop" role="presentation">
      <section className="batch-import-panel" role="dialog" aria-modal="true" aria-labelledby="batch-import-title">
        <header>
          <div><span className="eyebrow">本地批量导入</span><h2 id="batch-import-title">导入表单照片</h2></div>
          <button type="button" className="text-button" onClick={onClose}>关闭</button>
        </header>
        <div
          className={`batch-drop-zone ${dragging ? "dragging" : ""}`}
          onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => { event.preventDefault(); setDragging(false); addFiles(Array.from(event.dataTransfer.files)); }}
        >
          <strong>将多张照片拖到这里</strong>
          <span>支持 PNG、JPEG、TIFF；系统同时处理 3 张，单张失败不影响整批。</span>
          <div className="batch-picker-actions">
            <label className="button button-primary">选择多张照片<input aria-label="选择多张照片" type="file" multiple accept="image/png,image/jpeg,image/tiff" onChange={(event) => { addFiles(Array.from(event.target.files ?? [])); event.target.value = ""; }} /></label>
            <label className="button button-secondary">选择文件夹<input aria-label="选择文件夹" type="file" multiple accept="image/png,image/jpeg,image/tiff" {...{ webkitdirectory: "", directory: "" }} onChange={(event) => { addFiles(Array.from(event.target.files ?? [])); event.target.value = ""; }} /></label>
            <button type="button" className="button button-secondary" disabled title="局域网手机上传将在后续阶段启用">从手机上传（后续）</button>
          </div>
        </div>
        {items.length > 0 && <>
          <div className="batch-summary"><strong>本次导入 {counts.total} 张</strong><span>成功 {counts.succeeded}｜处理中 {counts.processing}｜需要处理 {counts.needsAction}｜失败 {counts.failed}</span></div>
          <div className="batch-item-list">
            {items.map((item) => <article key={item.id} className={`batch-item status-${item.status.toLowerCase()}`}>
              <div><strong>{item.file.name}</strong><span>{formatBytes(item.file.size)} · {statusLabel(item.status)}</span>{item.detail && <em>{item.detail}</em>}</div>
              {(item.status === "FAILED" || item.status === "NEEDS_ACTION") && <button type="button" className="button button-secondary" onClick={() => retry(item)}>重试此图</button>}
            </article>)}
          </div>
        </>}
      </section>
    </div>
  );
}

async function runPool<T>(items: T[], concurrency: number, worker: (item: T) => Promise<void>) {
  let index = 0;
  async function next(): Promise<void> {
    const current = index++;
    if (current >= items.length) return;
    await worker(items[current]);
    await next();
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, () => next()));
}

function countItems(items: LocalItem[]) {
  return {
    total: items.length,
    succeeded: items.filter((item) => item.status === "SUCCEEDED").length,
    processing: items.filter((item) => item.status === "QUEUED" || item.status === "PROCESSING").length,
    needsAction: items.filter((item) => item.status === "NEEDS_ACTION").length,
    failed: items.filter((item) => item.status === "FAILED").length,
  };
}

function statusLabel(status: ImportItemStatus) {
  return ({ QUEUED: "等待中", PROCESSING: "处理中", SUCCEEDED: "已导入", NEEDS_ACTION: "需要处理", FAILED: "失败" })[status];
}

function formatBytes(value: number) {
  return value < 1024 * 1024 ? `${Math.max(1, Math.round(value / 1024))} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`;
}
