import { useEffect, useState } from "react";

import {
  acknowledgePlantNotification,
  listPlantNotifications,
} from "./api";
import type { ManagementNotification } from "./types";
import { ErrorAlert, PageHeader } from "./shared/SummaryCardGrid";
import { GovernedDataTable } from "./shared/GovernedDataTable";
import type { DataColumn } from "./shared/GovernedDataTable";

export function AdminNotificationsPage() {
  const [items, setItems] = useState<ManagementNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [filterFactory, setFilterFactory] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "read" | "unread">("all");

  useEffect(() => {
    setLoading(true);
    setError("");
    listPlantNotifications()
      .then((result) => setItems(result.items))
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "通知加载失败"),
      )
      .finally(() => setLoading(false));
  }, []);

  async function acknowledge(item: ManagementNotification) {
    try {
      const updated = await acknowledgePlantNotification(item.notification_id);
      setItems((current) =>
        current.map((value) =>
          value.notification_id === updated.notification_id ? updated : value,
        ),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "知悉失败");
    }
  }

  function filteredItems(): ManagementNotification[] {
    return items.filter((item) => {
      if (
        filterFactory &&
        item.payload &&
        String((item.payload as Record<string, unknown>).factory_id ?? "") !== filterFactory
      ) {
        return false;
      }
      if (filterCategory && item.category !== filterCategory) {
        return false;
      }
      if (filterStatus === "read" && !item.read_at) {
        return false;
      }
      if (filterStatus === "unread" && item.read_at) {
        return false;
      }
      return true;
    });
  }

  const categoryOptions = [...new Set(items.map((i) => i.category))];

  const columns: DataColumn<ManagementNotification>[] = [
    {
      key: "created_at",
      header: "时间",
      render: (row) => row.created_at,
    },
    {
      key: "category",
      header: "类型",
      render: (row) => row.category,
    },
    {
      key: "title",
      header: "标题",
      render: (row) => row.title,
    },
    {
      key: "body",
      header: "内容",
      render: (row) => row.body.length > 60 ? `${row.body.slice(0, 60)}…` : row.body,
    },
    {
      key: "status",
      header: "状态",
      render: (row) =>
        row.read_at ? (
          <span className="notification-read">已知悉</span>
        ) : (
          <span className="notification-unread">未读</span>
        ),
    },
    {
      key: "actions",
      header: "操作",
      render: (row) =>
        !row.read_at ? (
          <button type="button" onClick={(e) => { e.stopPropagation(); void acknowledge(row); }}>
            确认知悉
          </button>
        ) : (
          <span className="notification-read-time">{row.read_at}</span>
        ),
    },
  ];

  return (
    <section className="admin-notifications-page">
      <PageHeader
        title="通知管理"
        subtitle="查看系统通知列表，按类型和状态筛选，确认知悉。"
      />

      {error && <ErrorAlert message={error} />}

      <div className="audit-filter-bar">
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
          类型
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
          >
            <option value="">全部类型</option>
            {categoryOptions.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </label>
        <label>
          状态
          <select
            value={filterStatus}
            onChange={(e) =>
              setFilterStatus(e.target.value as "all" | "read" | "unread")
            }
          >
            <option value="all">全部</option>
            <option value="unread">未读</option>
            <option value="read">已知悉</option>
          </select>
        </label>
        <button
          type="button"
          className="audit-filter-clear"
          onClick={() => {
            setFilterFactory("");
            setFilterCategory("");
            setFilterStatus("all");
          }}
        >
          清除筛选
        </button>
      </div>

      {loading ? (
        <p className="empty-state">加载中…</p>
      ) : (
        <GovernedDataTable
          columns={columns}
          rows={filteredItems()}
          rowKey={(row) => row.notification_id}
          emptyMessage="当前没有通知"
        />
      )}
    </section>
  );
}
