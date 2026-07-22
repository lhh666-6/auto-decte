import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  MobileApiError,
  mobileApiClient,
  type BambooDashboard,
  type BambooRecord,
  type BambooTaskBucket,
} from "@form-detection/api-client";

import { useMobileSession } from "../session/MobileSessionProvider";

const BUCKETS: Array<{ key: BambooTaskBucket; label: string }> = [
  { key: "available", label: "待处理" },
  { key: "waiting", label: "已签待后续" },
  { key: "completed", label: "已完成" },
];

export function BambooTaskListPage() {
  const navigate = useNavigate();
  const { sessionMetadata: session } = useMobileSession();
  const [bucket, setBucket] = useState<BambooTaskBucket>("available");
  const [dashboard, setDashboard] = useState<BambooDashboard>({
    available: 0,
    waiting: 0,
    completed: 0,
  });
  const [tasks, setTasks] = useState<BambooRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [baseInfo, setBaseInfo] = useState({
    cage_no: "",
    length: "",
    grade: "",
    bundle_count: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summary, result] = await Promise.all([
        mobileApiClient.getBambooDashboard(),
        mobileApiClient.listBambooTasks(bucket),
      ]);
      setDashboard(summary);
      setTasks(result.tasks);
    } catch (cause) {
      setError(message(cause, "无法加载竹丝工序任务，请检查网络后重试。"));
    } finally {
      setLoading(false);
    }
  }, [bucket]);

  useEffect(() => {
    void load();
  }, [load]);

  const createRecord = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const record = await mobileApiClient.createBambooRecord(
        {
          cage_no: baseInfo.cage_no,
          length: baseInfo.length,
          grade: baseInfo.grade,
          bundle_count: Number(baseInfo.bundle_count),
        },
        crypto.randomUUID(),
      );
      navigate(`/mobile/record/bamboo-process/${encodeURIComponent(record.record_id)}`);
    } catch (cause) {
      setError(message(cause, "新建记录失败，请重试。"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mobile-page bamboo-work-page">
      <header className="bamboo-page-heading">
        <div>
          <p>{session?.factory_name || "当前工厂"} · {roleLabel(session?.bamboo_role)}</p>
          <h2>记录工作</h2>
        </div>
        {session?.bamboo_role === "SORT_OPERATOR" && (
          <button type="button" className="bamboo-primary-action" onClick={() => setCreating((value) => !value)}>
            {creating ? "取消新建" : "+ 新建记录"}
          </button>
        )}
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}

      {creating && (
        <form className="bamboo-create-card" onSubmit={createRecord}>
          <h3>建立竹丝工序记录</h3>
          <div className="bamboo-field-grid">
            <label>竹笼号<input required value={baseInfo.cage_no} onChange={(event) => setBaseInfo({ ...baseInfo, cage_no: event.target.value })} /></label>
            <label>长度<input required inputMode="decimal" value={baseInfo.length} onChange={(event) => setBaseInfo({ ...baseInfo, length: event.target.value })} /></label>
            <label>等级<input required value={baseInfo.grade} onChange={(event) => setBaseInfo({ ...baseInfo, grade: event.target.value })} /></label>
            <label>捆数<input required type="number" inputMode="numeric" min="1" value={baseInfo.bundle_count} onChange={(event) => setBaseInfo({ ...baseInfo, bundle_count: event.target.value })} /></label>
          </div>
          <button type="submit" className="bamboo-sign-button" disabled={saving}>{saving ? "建立中…" : "建立并开始分选"}</button>
        </form>
      )}

      <nav className="bamboo-task-tabs" aria-label="任务分类">
        {BUCKETS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={bucket === item.key ? "active" : ""}
            onClick={() => setBucket(item.key)}
          >
            <span>{item.label}</span>
            <strong>{dashboard[item.key]}</strong>
          </button>
        ))}
      </nav>

      {loading ? (
        <div className="mobile-loading">加载任务中…</div>
      ) : tasks.length === 0 ? (
        <div className="mobile-empty"><p>当前分类暂无任务</p></div>
      ) : (
        <ul className="bamboo-task-list">
          {tasks.map((record) => (
            <li key={record.record_id}>
              <Link to={`/mobile/record/bamboo-process/${encodeURIComponent(record.record_id)}`} className="bamboo-task-card">
                <div className="bamboo-task-card-top">
                  <strong>{record.display_no}</strong>
                  <span>{stageLabel(record.current_stage)}</span>
                </div>
                <dl>
                  <div><dt>竹笼号</dt><dd>{String(record.base_info.cage_no || "—")}</dd></div>
                  <div><dt>等级</dt><dd>{String(record.base_info.grade || "—")}</dd></div>
                  <div><dt>捆数</dt><dd>{String(record.base_info.bundle_count || "—")}</dd></div>
                </dl>
                <small>更新时间 {formatTime(record.updated_at)}</small>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function stageLabel(stage: BambooRecord["current_stage"]): string {
  return ({
    SORT: "待分选",
    DIPPING: "待浸胶",
    DRYING: "待干燥",
    SUPERVISOR: "待主管审核",
    PLANT_AUDIT: "待厂长签字",
  } as const)[stage as Exclude<BambooRecord["current_stage"], null>] ?? "流程完成";
}

function roleLabel(role = ""): string {
  return ({
    SORT_OPERATOR: "分选工",
    DIPPING_OPERATOR: "浸胶工",
    DRYING_RACK_OPERATOR: "干燥工",
    INSPECTOR: "检测人",
    SUPERVISOR: "主管",
    PLANT_MANAGER: "厂长",
    FINANCE_APPROVER: "财务审批",
  } as Record<string, string>)[role] ?? role;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function message(cause: unknown, fallback: string): string {
  return cause instanceof MobileApiError ? cause.problem.detail : fallback;
}
