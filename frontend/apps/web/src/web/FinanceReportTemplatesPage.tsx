import { useEffect, useState } from "react";

import {
  confirmReportMapping,
  createReportMapping,
  listReportMappings,
  listReportTemplates,
} from "./api";
import type { ReportMappingVersion, ReportTemplateVersion } from "./types";
import "./report-template-pages.css";

export function FinanceReportTemplatesPage() {
  const [templates, setTemplates] = useState<ReportTemplateVersion[]>([]);
  const [mappings, setMappings] = useState<ReportMappingVersion[]>([]);
  useEffect(() => {
    void Promise.all([listReportTemplates(), listReportMappings()]).then(([a, b]) => {
      setTemplates(a.items);
      setMappings(b.items);
    });
  }, []);
  async function create(template: ReportTemplateVersion) {
    const sheet = template.structure.sheets[0]?.name;
    if (!sheet) return;
    const mapping = await createReportMapping(template.template_version_id, {
      sheet,
      start_row: 2,
      columns: [
        { column: 1, source_field: "subject_employee_code" },
        { column: 2, source_field: "business_date" },
      ],
    });
    setMappings((current) => [mapping, ...current]);
  }
  async function confirm(item: ReportMappingVersion) {
    const updated = await confirmReportMapping(item.mapping_version_id);
    setMappings((current) => current.map((value) => value.mapping_version_id === updated.mapping_version_id ? updated : value));
  }
  return (
    <section className="report-template-page">
      <header><h1>报表模板与映射</h1><p>映射独立版本化；模板结构变化不会静默复用旧映射。</p></header>
      <h2>已分析模板</h2>
      <div className="report-card-list">
        {templates.map((item) => <article key={item.template_version_id}><strong>{item.filename}</strong><span>{item.format} · {item.structure.sheets.map((sheet) => sheet.name).join("、")}</span><button type="button" onClick={() => void create(item)}>创建映射草稿</button></article>)}
      </div>
      <h2>映射版本</h2>
      <div className="report-card-list">
        {mappings.map((item) => <article key={item.mapping_version_id}><strong>映射 V{item.version}</strong><span>{item.mapping_json.sheet} · {item.status}</span>{item.status === "DRAFT" && <button type="button" onClick={() => void confirm(item)}>财务确认映射</button>}</article>)}
      </div>
    </section>
  );
}
