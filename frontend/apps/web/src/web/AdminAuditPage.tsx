import { useEffect, useState } from "react";

import { ErrorAlert, PageHeader } from "./shared/SummaryCardGrid";
import { DetailDrawer, DetailField } from "./shared/DetailDrawer";
import { GovernedDataTable } from "./shared/GovernedDataTable";
import type { DataColumn } from "./shared/GovernedDataTable";

interface AuditEntry {
  id: string;
  timestamp: string;
  actor_name: string;
  actor_code: string;
  action: string;
  object_type: string;
  object_id: string;
  factory_id: string;
  request_id: string;
  detail?: Record<string, unknown>;
}

export function AdminAuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);

  // Filters
  const [filterActor, setFilterActor] = useState("");
  const [filterFactory, setFilterFactory] = useState("");
  const [filterObject, setFilterObject] = useState("");
  const [filterAction, setFilterAction] = useState("");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    fetch("/api/v1/admin/audit-log", { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          const detail =
            typeof (body as Record<string, unknown>).detail === "string"
              ? (body as Record<string, unknown>).detail
              : "审计日志服务暂不可用";
          throw new Error(detail as string);
        }
        const data = (await response.json()) as { items: AuditEntry[] };
        setEntries(data.items ?? []);
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "审计日志加载失败");
      })
      .finally(() => setLoading(false));
  }, []);

  function filteredEntries(): AuditEntry[] {
    return entries.filter((entry) => {
      if (filterActor && !entry.actor_name.toLowerCase().includes(filterActor.toLowerCase()) && !entry.actor_code.toLowerCase().includes(filterActor.toLowerCase())) {
        return false;
      }
      if (filterFactory && entry.factory_id !== filterFactory) {
        return false;
      }
      if (filterObject && !entry.object_type.toLowerCase().includes(filterObject.toLowerCase()) && !entry.object_id.toLowerCase().includes(filterObject.toLowerCase())) {
        return false;
      }
      if (filterAction && !entry.action.toLowerCase().includes(filterAction.toLowerCase())) {
        return false;
      }
      if (filterDateFrom && entry.timestamp < filterDateFrom) {
        return false;
      }
      if (filterDateTo && entry.timestamp > filterDateTo + "T23:59:59") {
        return false;
      }
      return true;
    });
  }

  const columns: DataColumn<AuditEntry>[] = [
    {
      key: "timestamp",
      header: "时间",
      render: (row) => row.timestamp,
    },
    {
      key: "actor",
      header: "操作者",
      render: (row) => row.actor_name,
    },
    {
      key: "action",
      header: "动作",
      render: (row) => row.action,
    },
    {
      key: "object",
      header: "对象",
      render: (row) => `${row.object_type}:${row.object_id}`,
    },
    {
      key: "factory",
      header: "工厂",
      render: (row) => row.factory_id,
    },
    {
      key: "request_id",
      header: "请求编号",
      render: (row) => row.request_id,
    },
  ];

  return (
    <section className="admin-audit-page">
      <PageHeader
        title="审计日志"
        subtitle="查看系统操作的审计记录，按条件筛选并点击行查看详情。"
      />

      {error && <ErrorAlert message={error} />}

      {/* Filters */}
      <div className="audit-filter-bar">
        <label>
          操作者
          <input
            type="text"
            placeholder="姓名或工号"
            value={filterActor}
            onChange={(e) => setFilterActor(e.target.value)}
          />
        </label>
        <label>
          工厂
          <input
            type="text"
            placeholder="工厂 ID"
            value={filterFactory}
            onChange={(e) => setFilterFactory(e.target.value)}
          />
        </label>
        <label>
          对象
          <input
            type="text"
            placeholder="对象类型或 ID"
            value={filterObject}
            onChange={(e) => setFilterObject(e.target.value)}
          />
        </label>
        <label>
          动作
          <input
            type="text"
            placeholder="操作类型"
            value={filterAction}
            onChange={(e) => setFilterAction(e.target.value)}
          />
        </label>
        <label>
          时间起
          <input
            type="date"
            value={filterDateFrom}
            onChange={(e) => setFilterDateFrom(e.target.value)}
          />
        </label>
        <label>
          时间止
          <input
            type="date"
            value={filterDateTo}
            onChange={(e) => setFilterDateTo(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="audit-filter-clear"
          onClick={() => {
            setFilterActor("");
            setFilterFactory("");
            setFilterObject("");
            setFilterAction("");
            setFilterDateFrom("");
            setFilterDateTo("");
          }}
        >
          清除筛选
        </button>
      </div>

      {loading ? (
        <p className="empty-state">加载中…</p>
      ) : entries.length === 0 && !error ? (
        <p className="empty-state">审计日志服务尚未接入，当前无记录。</p>
      ) : (
        <GovernedDataTable
          columns={columns}
          rows={filteredEntries()}
          rowKey={(row) => row.id}
          onRowClick={setSelectedEntry}
          emptyMessage="无匹配的审计记录"
        />
      )}

      <DetailDrawer
        open={selectedEntry !== null}
        onClose={() => setSelectedEntry(null)}
        title="审计记录详情"
      >
        {selectedEntry && (
          <div className="detail-drawer-fields">
            <DetailField label="时间" value={selectedEntry.timestamp} />
            <DetailField label="操作者" value={selectedEntry.actor_name} />
            <DetailField label="操作者工号" value={selectedEntry.actor_code} />
            <DetailField label="动作" value={selectedEntry.action} />
            <DetailField label="对象类型" value={selectedEntry.object_type} />
            <DetailField label="对象 ID" value={selectedEntry.object_id} />
            <DetailField label="工厂" value={selectedEntry.factory_id} />
            <DetailField label="请求编号" value={selectedEntry.request_id} />
          </div>
        )}
      </DetailDrawer>
    </section>
  );
}
