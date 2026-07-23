import { useEffect, useState } from "react";

import {
  createGovernedExport,
  listGovernedExports,
  listReportMappings,
} from "./api";
import type { GovernedExportBatch, ReportMappingVersion } from "./types";
import "./report-template-pages.css";

export function FinanceGovernedExportsPage() {
  const [mappings, setMappings] = useState<ReportMappingVersion[]>([]);
  const [batches, setBatches] = useState<GovernedExportBatch[]>([]);
  useEffect(() => {
    void Promise.all([listReportMappings(), listGovernedExports()]).then(([a, b]) => {
      setMappings(a.items.filter((item) => item.status === "CONFIRMED"));
      setBatches(b.items);
    });
  }, []);
  async function create(item: ReportMappingVersion) {
    const batch = await createGovernedExport(
      item.template_version_id, item.mapping_version_id, "",
    );
    setBatches((current) => [batch, ...current]);
  }
  return (
    <section className="report-template-page">
      <header><h1>正式报表导出</h1><p>导出冻结模板、映射、筛选和数据水位；只有重开校验通过的文件可下载。</p></header>
      <div className="report-card-list">
        {mappings.map((item) => <article key={item.mapping_version_id}><strong>映射 V{item.version}</strong><button type="button" onClick={() => void create(item)}>生成正式导出</button></article>)}
      </div>
      <h2>导出历史</h2>
      <div className="report-card-list">
        {batches.map((item) => <article key={item.export_batch_id}><strong>{item.download_name}</strong><span>{item.status} · 水位 {item.data_watermark}</span>{item.status === "AVAILABLE" && <a href={`/api/v1/finance/exports/${item.export_batch_id}/download`}>下载</a>}<a href={`/api/v1/finance/exports/${item.export_batch_id}/lineage`}>查看血缘</a></article>)}
      </div>
    </section>
  );
}
