import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { MobileApiError, mobileApiClient, type BambooDashboard, type BambooRecord, type BambooTaskBucket } from "@form-detection/api-client";

import { createMobileClientId } from "../device";
import { useMobileSession } from "../session/MobileSessionProvider";

const BUCKETS: Array<{ key: BambooTaskBucket; label: string }> = [
  { key: "available", label: "可记录" },
  { key: "waiting", label: "等待上游" },
  { key: "completed", label: "已完成" },
];

export function BambooTaskListPage() {
  const navigate = useNavigate();
  const { sessionMetadata: session } = useMobileSession();
  const [bucket, setBucket] = useState<BambooTaskBucket>("available");
  const [dashboard, setDashboard] = useState<BambooDashboard>({ available: 0, waiting: 0, completed: 0 });
  const [tasks, setTasks] = useState<BambooRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [baseInfo, setBaseInfo] = useState({ cage_no: "", length: "", grade: "", bundle_count: "" });

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
      setError(message(cause, "无法加载工作记录，请检查网络后重试。"));
    } finally {
      setLoading(false);
    }
  }, [bucket]);

  useEffect(() => { void load(); }, [load]);

  const createRecord = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const created = await mobileApiClient.createBambooRecord(
        { ...baseInfo, bundle_count: Number(baseInfo.bundle_count) },
        createMobileClientId("record"),
      );
      navigate(`/mobile/records/${encodeURIComponent(created.record_id)}`);
    } catch (cause) {
      setError(message(cause, "新建记录失败，请重试。"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page bamboo-work-page">
      <h2 className="visually-hidden">记录工作</h2>
      <section className="section">
        <div className="section-head">
          <div>
            <div className="section-title">{workTitle(session?.bamboo_role)}</div>
            <div className="section-note">{workDescription(session?.bamboo_role)}</div>
          </div>
          {session?.bamboo_role === "SORT_OPERATOR" && (
            <button type="button" className="btn primary small" onClick={() => setCreating(true)} aria-label="新建竹丝记录">新建</button>
          )}
        </div>
        <div className="section-note">{session?.factory_name || "当前工厂"} · {roleLabel(session?.bamboo_role)}</div>
      </section>

      {error && <div className="banner danger" role="alert">{error}</div>}

      <nav className="tabs" aria-label="工作分类">
        {BUCKETS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`tab${bucket === item.key ? " on" : ""}`}
            onClick={() => setBucket(item.key)}
          >
            {item.label} {dashboard[item.key]}
          </button>
        ))}
      </nav>

      {loading ? (
        <div className="mobile-loading">加载工作中…</div>
      ) : tasks.length === 0 ? (
        <div className="card empty">
          <h3>当前分类暂无记录</h3>
          <p>前面流程完成后，后续岗位才会看到对应记录。</p>
        </div>
      ) : (
        <div className="list" aria-label="竹丝记录列表">
          {tasks.map((record) => (
            <Link to={`/mobile/records/${encodeURIComponent(record.record_id)}`} className="record-card" key={record.record_id}>
              <div className="record-top">
                <div>
                  <div className="record-no">{record.display_no}</div>
                  <div className="record-meta">
                    竹笼号 {String(record.base_info.cage_no || "—")} · 等级 {String(record.base_info.grade || "—")} · 捆数 {String(record.base_info.bundle_count || "—")}
                    <br />
                    当前流程：{stageLabel(record.current_stage)} · 更新于 {formatTime(record.updated_at)}
                  </div>
                </div>
                <span className={`chip ${bucket === "available" ? "info" : bucket === "waiting" ? "wait" : "ok"}`}>{bucketLabel(bucket)}</span>
              </div>
              <div className="record-actions">
                <span className="btn primary small">{bucket === "available" ? "去记录" : "查看表单"}</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {creating && (
        <div className="bamboo-v3-sheet-backdrop" role="presentation">
          <form className="bamboo-v3-bottom-sheet" onSubmit={createRecord} role="dialog" aria-modal="true" aria-label="新建竹丝记录">
            <div className="bamboo-v3-sheet-handle" />
            <header><h3>新建竹丝工序记录</h3><button type="button" aria-label="关闭" onClick={() => setCreating(false)}>×</button></header>
            <div className="bamboo-field-grid">
              <label>竹笼号<input required value={baseInfo.cage_no} onChange={(event) => setBaseInfo({ ...baseInfo, cage_no: event.target.value })} /></label>
              <label>长度<input required inputMode="decimal" value={baseInfo.length} onChange={(event) => setBaseInfo({ ...baseInfo, length: event.target.value })} /></label>
              <label>等级<input required value={baseInfo.grade} onChange={(event) => setBaseInfo({ ...baseInfo, grade: event.target.value })} /></label>
              <label>捆数<input required type="number" min="1" value={baseInfo.bundle_count} onChange={(event) => setBaseInfo({ ...baseInfo, bundle_count: event.target.value })} /></label>
            </div>
            <button type="submit" className="bamboo-sign-button" disabled={saving}>{saving ? "建立中…" : "建立并开始分选"}</button>
          </form>
        </div>
      )}
    </div>
  );
}

function workTitle(role = ""): string {
  if (role === "INSPECTOR") return "记录随机检测";
  if (role === "SUPERVISOR" || role === "PLANT_MANAGER") return "待把关记录";
  return `记录${roleStageLabel(role)}工序`;
}

function workDescription(role = ""): string {
  if (role === "INSPECTOR") return "随机检测为选做，不阻断主流程";
  if (role === "SUPERVISOR" || role === "PLANT_MANAGER") return "上游完成后，本环节才可以处理";
  return "仅显示本人岗位允许填写的工序和生产对象";
}

function roleStageLabel(role = ""): string {
  return ({ SORT_OPERATOR: "分选/装笼", DIPPING_OPERATOR: "浸胶", DRYING_RACK_OPERATOR: "干燥装架" } as Record<string, string>)[role] ?? "";
}

function bucketLabel(bucket: BambooTaskBucket): string {
  return ({ available: "可记录", waiting: "等待上游", completed: "已完成" } as Record<BambooTaskBucket, string>)[bucket];
}

function stageLabel(stage: BambooRecord["current_stage"]): string {
  return ({ SORT: "待分选", DIPPING: "待浸胶", DRYING: "待干燥", SUPERVISOR: "待主管审核", PLANT_AUDIT: "待厂长签字" } as Record<string, string>)[stage ?? ""] ?? "流程完成";
}

function roleLabel(role = ""): string {
  return ({ SORT_OPERATOR: "分选工", DIPPING_OPERATOR: "浸胶工", DRYING_RACK_OPERATOR: "干燥工", INSPECTOR: "检测人", SUPERVISOR: "主管", PLANT_MANAGER: "厂长" } as Record<string, string>)[role] ?? role;
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function message(cause: unknown, fallback: string): string {
  return cause instanceof MobileApiError ? cause.problem.detail : fallback;
}
