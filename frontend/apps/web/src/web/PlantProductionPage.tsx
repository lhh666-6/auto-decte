import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getPlantProduction, returnPlantRecord } from "./api";
import type { BambooProductionRecord } from "./types";
import "./ledger-pages.css";

const STAGES: Record<BambooProductionRecord["form_type"], Array<[string, string]>> = {
  SORTING: [["SORT", "分选"]],
  DIPPING_DRYING: [["DIPPING", "浸胶"], ["DRYING", "干燥"]],
};

const STAGE_LABELS: Record<string, string> = {
  SORT: "分选",
  DIPPING: "浸胶",
  DRYING: "干燥",
  SUPERVISOR: "主管审核",
  PLANT_AUDIT: "厂长签字",
};

const STATUS_LABELS: Record<string, string> = {
  ACTIVE: "进行中",
  COMPLETED: "已完成",
};

export function PlantProductionPage() {
  const [records, setRecords] = useState<BambooProductionRecord[]>([]);
  const [overview, setOverview] = useState({ total: 0, active: 0, completed: 0 });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<BambooProductionRecord | null>(null);
  const [targetStages, setTargetStages] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  // 筛选状态
  const [cageQuery, setCageQuery] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  function reload() {
    setLoading(true);
    void getPlantProduction().then((result) => {
      setRecords(result.records);
      setOverview(result.overview);
      setLoading(false);
    }).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "生产数据加载失败");
      setLoading(false);
    });
  }
  useEffect(reload, []);

  // 客户端筛选
  const filteredRecords = useMemo(() => {
    let result = records;
    if (cageQuery.trim()) {
      const q = cageQuery.trim().toLowerCase();
      result = result.filter((r) => (r.cage_no || "").toLowerCase().includes(q));
    }
    if (stageFilter) {
      result = result.filter((r) => r.current_stage === stageFilter);
    }
    if (statusFilter) {
      result = result.filter((r) => r.status === statusFilter);
    }
    return result;
  }, [records, cageQuery, stageFilter, statusFilter]);

  async function submitReturn() {
    if (!selected || !reason.trim() || !targetStages.length) return;
    try {
      await returnPlantRecord(selected.record_id, targetStages, reason, selected.revision);
      setSelected(null);
      setTargetStages([]);
      setReason("");
      reload();
    } catch (cause) {
      const msg = cause instanceof Error ? cause.message : "打回失败";
      if (msg.includes("STALE_REVISION") || msg.includes("revision")) {
        setError("记录已被修改，列表已刷新。请重试。");
        reload();
      } else {
        setError(msg);
      }
    }
  }

  // 构建阶段筛选选项（从所有记录中收集）
  const availableStages = useMemo(() => {
    const stages = new Set<string>();
    for (const r of records) {
      if (r.current_stage) stages.add(r.current_stage);
    }
    return Array.from(stages);
  }, [records]);

  return (
    <section className="ledger-page">
      <header>
        <h1>本厂竹丝生产看板</h1>
        <p>与工人移动端共用生产记录；厂长可选择需要重做的环节。</p>
      </header>
      {error && <div role="alert">{error}</div>}
      {loading && <div role="status">正在加载生产数据…</div>}

      <div className="ledger-summary">
        <article><span>全部</span><strong>{overview.total}</strong></article>
        <article><span>进行中</span><strong>{overview.active}</strong></article>
        <article><span>已完成</span><strong>{overview.completed}</strong></article>
      </div>

      {/* 筛选栏 */}
      <div className="ledger-filters">
        <label>
          笼号搜索
          <input
            type="search"
            value={cageQuery}
            onChange={(event) => setCageQuery(event.target.value)}
            placeholder="输入笼号搜索…"
          />
        </label>
        <label>
          当前阶段
          <select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)}>
            <option value="">全部阶段</option>
            {availableStages.map((stage) => (
              <option key={stage} value={stage}>
                {STAGE_LABELS[stage] ?? stage}
              </option>
            ))}
          </select>
        </label>
        <label>
          状态
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">全部状态</option>
            <option value="ACTIVE">进行中</option>
            <option value="COMPLETED">已完成</option>
          </select>
        </label>
      </div>

      {/* 生产列表 */}
      <div className="ledger-case-list">
        {!loading && filteredRecords.length === 0 && !error && (
          <div className="ledger-empty">
            {records.length === 0 ? (
              <>
                <p><strong>当前工厂还没有生产记录。</strong></p>
                <p className="signature-muted">工人通过移动端提交的生产数据会在此处显示。请确认移动端已配置正确的工厂信息。</p>
              </>
            ) : (
              <>
                <p><strong>没有匹配的生产记录。</strong></p>
                <p className="signature-muted">请尝试调整筛选条件，或清除搜索关键词后重试。</p>
              </>
            )}
          </div>
        )}
        {filteredRecords.map((record) => (
          <article key={record.record_id}>
            <div className="ledger-record-info">
              <strong>{record.display_no} · 笼号 {record.cage_no || "—"}</strong>
              <span className="ledger-tags">
                <span className="ledger-tag ledger-tag-stage">
                  {STAGE_LABELS[record.current_stage ?? ""] ?? record.current_stage ?? "已完成"}
                </span>
                <span className={`ledger-tag ${record.status === "ACTIVE" ? "ledger-tag-active" : "ledger-tag-done"}`}>
                  {STATUS_LABELS[record.status] ?? record.status}
                </span>
              </span>
            </div>
            <div className="ledger-record-actions">
              <Link to={`/plant/production/${record.record_id}`}>
                {record.current_stage === "PLANT_AUDIT" ? "查看并签字" : "查看详情"}
              </Link>
              <button type="button" className="secondary-button" onClick={() => {
                setSelected(record);
                setTargetStages([]);
              }}>选择环节打回</button>
            </div>
          </article>
        ))}
      </div>

      {/* 打回面板 */}
      {selected && (
        <div className="ledger-return-panel">
          <h2>打回 {selected.display_no}（笼号 {selected.cage_no || "—"} · 版本 {selected.revision}）</h2>
          <fieldset>
            <legend>选择要打回的环节</legend>
            {STAGES[selected.form_type].map(([value, label]) => (
              <label key={value}>
                <input
                  type="checkbox"
                  aria-label={label}
                  checked={targetStages.includes(value)}
                  onChange={(event) => setTargetStages((current) => (
                    event.target.checked
                      ? [...current, value]
                      : current.filter((item) => item !== value)
                  ))}
                />
                {label}
              </label>
            ))}
          </fieldset>
          <label>
            打回原因
            <textarea
              aria-label="打回原因"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="必填：说明打回原因"
            />
          </label>
          <p className="signature-muted">打回将撤销选中环节的有效提交，记录将回退至最早被选中环节。</p>
          <div className="ledger-return-actions">
            <button
              type="button"
              disabled={!reason.trim() || !targetStages.length}
              onClick={() => void submitReturn()}
            >确认打回</button>
            <button type="button" className="secondary-button" onClick={() => {
              setSelected(null);
              setTargetStages([]);
              setReason("");
            }}>取消</button>
          </div>
        </div>
      )}
    </section>
  );
}
