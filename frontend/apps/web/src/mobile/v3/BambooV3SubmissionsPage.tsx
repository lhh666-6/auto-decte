import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { mobileApiClient, type BambooHistoryItem } from "@form-detection/api-client";

import { getMobileDeviceId } from "../device";
import { useMobileSession } from "../session/MobileSessionProvider";
import { countBambooDrafts } from "../storage/bambooDrafts";

export function BambooV3SubmissionsPage() {
  const { sessionMetadata } = useMobileSession();
  const [items, setItems] = useState<BambooHistoryItem[]>([]);
  const [draftCount, setDraftCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const isInspector = sessionMetadata?.bamboo_role === "INSPECTOR";

  const load = useCallback(async () => {
    if (!sessionMetadata) return;
    setLoading(true);
    setError("");
    try {
      setItems(await mobileApiClient.listBambooHistory());
    } catch {
      setError("无法加载历史记录，本机草稿仍会保留。");
    } finally {
      setDraftCount(countBambooDrafts(sessionMetadata.employee_code, sessionMetadata.factory_id, getMobileDeviceId()));
      setLoading(false);
    }
  }, [sessionMetadata]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const refresh = () => setDraftCount(sessionMetadata ? countBambooDrafts(sessionMetadata.employee_code, sessionMetadata.factory_id, getMobileDeviceId()) : 0);
    window.addEventListener("bamboo-drafts-changed", refresh);
    return () => window.removeEventListener("bamboo-drafts-changed", refresh);
  }, [sessionMetadata]);

  return (
    <div className="page bamboo-v3-submissions">
      <h2 className="visually-hidden">历史记录</h2>
      <section className="section">
        <div className="section-head"><div><div className="section-title">{isInspector ? "我的检测记录" : "我的历史记录"}</div><div className="section-note">{isInspector ? "本人完成的质量检测记录" : "本人完成的签字和检测均在这里保留"}</div></div><div className="section-note">{items.length} 条</div></div>
        <div className="stats submissions-stats"><div className="stat"><b>{draftCount}</b><span>自动保存草稿</span></div><div className="stat"><b>{items.length}</b><span>历史记录</span></div></div>
      </section>
      {error && <div className="banner danger" role="alert">{error}<button type="button" className="btn small secondary" onClick={() => void load()}>重试</button></div>}
      {loading ? <div className="mobile-loading">加载中…</div> : items.length === 0 ? (
        <div className="card empty"><h3>{isInspector ? "暂无检测记录" : "暂无历史记录"}</h3><p>{isInspector ? "完成质量检测后，会在这里显示。" : "完成工序签字或检测后，会在这里显示。"}</p><Link className="btn primary full" to="/mobile/work">{isInspector ? "去检测" : "记录我的工作"}</Link></div>
      ) : (
        <div className="list">{items.map((item) => (
          <Link className="record-card" to={`/mobile/records/${encodeURIComponent(item.record_id)}`} key={item.activity_id}>
            <div className="record-top"><div><div className="record-no">{item.display_no}</div><div className="record-meta">笼号 {item.cage_no || "—"} · {actionLabel(item.action)}<br />{formatTime(item.submitted_at)}</div></div><span className={`chip ${item.status === "COMPLETED" ? "ok" : "wait"}`}>{stateLabel(item)}</span></div>
          </Link>
        ))}</div>
      )}
    </div>
  );
}

function actionLabel(action: string): string {
  return ({ SORT: "分选签字", DIPPING: "浸胶签字", DRYING: "干燥签字", SUPERVISOR: "主管签字", PLANT_AUDIT: "厂长确认", INSPECTION: "检测留痕" } as Record<string, string>)[action] ?? action;
}

function stateLabel(item: BambooHistoryItem): string {
  if (item.status === "COMPLETED") return "流程完成";
  return ({ SORT: "待分选", DIPPING: "待浸胶", DRYING: "待干燥", SUPERVISOR: "待主管", PLANT_AUDIT: "待厂长确认" } as Record<string, string>)[item.current_stage ?? ""] ?? "已流转";
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
