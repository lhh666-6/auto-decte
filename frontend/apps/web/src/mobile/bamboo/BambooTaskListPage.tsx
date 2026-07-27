import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  MobileApiError,
  mobileApiClient,
  type BambooDashboard,
  type BambooInspectionWindow,
  type BambooRecord,
  type BambooRecordPresetOptions,
  type BambooTaskBucket,
} from "@form-detection/api-client";

import { createMobileClientId, getMobileDeviceId } from "../device";
import { useMobileSession } from "../session/MobileSessionProvider";
import { clearBambooDraft, readBambooDraft, writeBambooDraft, type BambooDraftScope } from "../storage/bambooDrafts";

function getBuckets(role: string): Array<{ key: BambooTaskBucket; label: string }> {
  if (role === "INSPECTOR") {
    return [
      { key: "available", label: "可检测" },
      { key: "waiting", label: "等待检测条件" },
      { key: "completed", label: "我的检测记录" },
    ];
  }
  // DIPPING_OPERATOR: dipping is the first stage, no "waiting" concept
  if (role === "DIPPING_OPERATOR") {
    return [
      { key: "available", label: "待浸胶" },
      { key: "completed", label: "我的记录" },
    ];
  }
  // DRYING_RACK_OPERATOR: waits for DIPPING to complete
  if (role === "DRYING_RACK_OPERATOR") {
    return [
      { key: "available", label: "待干燥" },
      { key: "waiting", label: "等待浸胶" },
      { key: "completed", label: "我的记录" },
    ];
  }
  return [
    { key: "available", label: "可记录" },
    { key: "waiting", label: "等待上游" },
    { key: "completed", label: "我的记录" },
  ];
}

type PickerKey = "special_classes" | "length" | "shade" | "grade";
type BaseInfoDraft = {
  mode: "分选" | "分选+装笼";
  special_classes: string[];
  length: string;
  shade: string;
  grade: string;
  supplier: string;
  cage_no: string;
  bundle_count: string;
};

type PendingSortingSubmission = {
  ownerEmployeeCode: string;
  factoryId: string;
  deviceId: string;
  createKey: string;
  stageKey: string;
  draft: BaseInfoDraft;
  moisture: string[];
  baseInfo: Record<string, unknown>;
  createdRecord?: BambooRecord;
};

const PENDING_SORTING_STORAGE_PREFIX = "bamboo-v3-pending-sorting-submission";

const EMPTY_DRAFT: BaseInfoDraft = {
  mode: "分选",
  special_classes: [],
  length: "",
  shade: "",
  grade: "",
  supplier: "",
  cage_no: "",
  bundle_count: "",
};

export function BambooTaskListPage() {
  const navigate = useNavigate();
  const { sessionMetadata: session } = useMobileSession();
  const [deviceId] = useState(() => getMobileDeviceId());
  const loadGeneration = useRef(0);
  const restoredScope = useRef("");
  const [bucket, setBucket] = useState<BambooTaskBucket>("available");
  const [cageQuery, setCageQuery] = useState("");
  const [searchedCage, setSearchedCage] = useState("");
  const [dashboard, setDashboard] = useState<BambooDashboard>({ available: 0, waiting: 0, completed: 0 });
  const [tasks, setTasks] = useState<BambooRecord[]>([]);
  const [inspectionWindows, setInspectionWindows] = useState<BambooInspectionWindow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [picker, setPicker] = useState<PickerKey | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [editCageNo, setEditCageNo] = useState(false);
  const [cageNoOverride, setCageNoOverride] = useState("");
  const [presets, setPresets] = useState<BambooRecordPresetOptions | null>(null);
  const [presetsLoading, setPresetsLoading] = useState(false);
  const [presetsError, setPresetsError] = useState("");
  const [baseInfo, setBaseInfo] = useState<BaseInfoDraft>(EMPTY_DRAFT);
  const [moisture, setMoisture] = useState(() => Array.from({ length: 8 }, () => ""));
  const [createIdempotencyKey, setCreateIdempotencyKey] = useState("");
  const [stageIdempotencyKey, setStageIdempotencyKey] = useState("");
  const [pendingSubmission, setPendingSubmission] = useState<PendingSortingSubmission | null>(null);
  // V1: ALL roles see available records directly. Cage search is optional filtering.
  const isInspector = session?.bamboo_role === "INSPECTOR";
  const roleSupportsCageSearch = ["DIPPING_OPERATOR", "DRYING_RACK_OPERATOR", "INSPECTOR"].includes(session?.bamboo_role ?? "") && bucket === "available";
  const buckets = getBuckets(session?.bamboo_role ?? "");
  const sortingDraftScope = useMemo<BambooDraftScope | null>(() => session ? ({
    employeeCode: session.employee_code,
    factoryId: session.factory_id,
    deviceId,
    recordId: "new-sorting",
    stage: "SORT_CREATE",
  }) : null, [deviceId, session]);
  const scopedPendingSubmission = pendingSubmission
    && pendingSubmission.ownerEmployeeCode === session?.employee_code
    && pendingSubmission.factoryId === session?.factory_id
    && pendingSubmission.deviceId === deviceId
    ? pendingSubmission
    : null;
  const hasPendingSubmission = scopedPendingSubmission !== null;
  const createdRecord = scopedPendingSubmission?.createdRecord ?? null;
  const createSheetVisible = creating && (pendingSubmission === null || scopedPendingSubmission !== null);

  const netWeight = useMemo(() => {
    const bundles = Number(baseInfo.bundle_count);
    const factor = Number(presets?.weight_factors[baseInfo.length]);
    if (!Number.isFinite(bundles) || bundles <= 0 || !Number.isFinite(factor)) return null;
    return { value: bundles * factor, factor };
  }, [baseInfo.bundle_count, baseInfo.length, presets]);

  const moistureValues = useMemo(
    () => moisture.filter((value) => value.trim() !== "").map(Number),
    [moisture],
  );
  const moistureAverage = useMemo(
    () => moistureValues.length > 0
      ? (moistureValues.reduce((total, value) => total + value, 0) / moistureValues.length).toFixed(1)
      : null,
    [moistureValues],
  );
  const pendingNetWeight = Number(scopedPendingSubmission?.baseInfo.net_weight);
  const summaryNetWeight = netWeight?.value ?? (Number.isFinite(pendingNetWeight) ? pendingNetWeight : null);

  const load = useCallback(async () => {
    if (!session?.bamboo_role) return;
    const generation = ++loadGeneration.current;
    setLoading(true);
    setError("");
    setLoaded(false);
    try {
      if (isInspector && bucket !== "waiting") {
        const queueBucket = bucket === "available" ? "active" : "history";
        const [summary, queue] = await Promise.all([
          mobileApiClient.getBambooDashboard(),
          mobileApiClient.listBambooInspectionQueue(queueBucket, searchedCage),
        ]);
        if (generation !== loadGeneration.current) return;
        setDashboard(summary);
        setInspectionWindows(queue.items);
        setTasks([]);
        setLoaded(true);
        if (searchedCage && queue.items.length === 1) {
          navigate(`/mobile/records/${encodeURIComponent(queue.items[0].record_id)}`);
          return;
        }
      } else {
        const [summary, result] = await Promise.all([
          mobileApiClient.getBambooDashboard(),
          roleSupportsCageSearch && searchedCage
            ? mobileApiClient.listBambooTasks(bucket, searchedCage)
            : mobileApiClient.listBambooTasks(bucket),
        ]);
        if (generation !== loadGeneration.current) return;
        setDashboard(summary);
        setTasks(result.tasks);
        setInspectionWindows([]);
        setLoaded(true);
        if (searchedCage && result.tasks.length === 1) {
          navigate(`/mobile/records/${encodeURIComponent(result.tasks[0].record_id)}`);
          return;
        }
      }
    } catch (cause) {
      if (generation !== loadGeneration.current) return;
      setError(message(cause, "无法加载工作记录，请检查网络后重试。"));
    } finally {
      if (generation === loadGeneration.current) setLoading(false);
    }
  }, [bucket, isInspector, roleSupportsCageSearch, searchedCage, session?.bamboo_role, navigate]);

  const loadPresets = useCallback(async () => {
    setPresetsLoading(true);
    setPresetsError("");
    setPresets(null);
    try {
      setPresets(await mobileApiClient.getBambooRecordOptions());
    } catch (cause) {
      const detail = message(cause, "网络请求失败");
      setPresetsError(`后台发布选项加载失败：${detail}。当前不能新建表单，请重新加载。`);
    } finally {
      setPresetsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    return () => { loadGeneration.current += 1; };
  }, [load]);

  useEffect(() => {
    if (!session?.employee_code || !session.factory_id) return;
    const scope = pendingStorageKey(session.employee_code, session.factory_id, deviceId);
    if (restoredScope.current === scope) return;
    restoredScope.current = scope;
    const restored = readPendingSortingSubmission(session.employee_code, session.factory_id, deviceId);
    setPendingSubmission(restored);
    if (!restored) {
      setCreating(false);
      setConfirming(false);
      setPicker(null);
      setBaseInfo(EMPTY_DRAFT);
      setMoisture(Array.from({ length: 8 }, () => ""));
      setFormError("");
      return;
    }
    setBaseInfo(restored.draft);
    setMoisture(restored.moisture);
    setCreateIdempotencyKey(restored.createKey);
    setStageIdempotencyKey(restored.stageKey);
    setFormError("发现一条属于当前账号、工厂和设备的未完成分选提交，请继续提交或稍后处理。");
    setConfirming(true);
    setPicker(null);
    setCreating(true);
  }, [deviceId, session?.employee_code, session?.factory_id]);

  useEffect(() => {
    if (!creating || hasPendingSubmission || !sortingDraftScope) return;
    writeBambooDraft(sortingDraftScope, { baseInfo, moisture });
  }, [baseInfo, creating, hasPendingSubmission, moisture, sortingDraftScope]);

  const closeCreateSheet = useCallback(() => {
    if (saving) return;
    setCreating(false);
    setConfirming(false);
    setPicker(null);
  }, [saving]);

  useEffect(() => {
    if (!creating) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || saving) return;
      event.preventDefault();
      closeCreateSheet();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeCreateSheet, creating, saving]);

  const openCreateSheet = () => {
    if (!session?.employee_code || !session.factory_id) {
      setError("当前身份尚未加载完成，暂时不能新建记录。");
      return;
    }
    const restored = scopedPendingSubmission ?? readPendingSortingSubmission(session.employee_code, session.factory_id, deviceId);
    if (restored) {
      setPendingSubmission(restored);
      setBaseInfo(restored.draft);
      setMoisture(restored.moisture);
      setCreateIdempotencyKey(restored.createKey);
      setStageIdempotencyKey(restored.stageKey);
      setFormError("发现一条未完成的分选提交；继续时会复用原请求，不会重复建表。");
      setConfirming(true);
      setPicker(null);
      setCreating(true);
      return;
    }
    const savedDraft = sortingDraftScope ? readBambooDraft<{ baseInfo: BaseInfoDraft; moisture: string[] }>(sortingDraftScope) : null;
    setBaseInfo(savedDraft?.baseInfo && isBaseInfoDraft(savedDraft.baseInfo) ? savedDraft.baseInfo : EMPTY_DRAFT);
    setMoisture(Array.isArray(savedDraft?.moisture) ? savedDraft!.moisture : Array.from({ length: 8 }, () => ""));
    setCreateIdempotencyKey(createMobileClientId("sorting-record"));
    setStageIdempotencyKey(createMobileClientId("sorting-stage"));
    setPendingSubmission(null);
    setFormError("");
    setPresets(null);
    setPresetsError("");
    setConfirming(false);
    setEditCageNo(false);
    setCageNoOverride("");
    setPicker(null);
    setCreating(true);
    void loadPresets();
  };

  const requestConfirm = (event: React.FormEvent) => {
    event.preventDefault();
    if (!presets) {
      setFormError("后台发布选项尚未成功加载，不能提交。请重新加载后再试。");
      return;
    }
    const validation = validateDraft(baseInfo, moisture);
    if (validation) {
      setFormError(validation);
      return;
    }
    setFormError("");
    setConfirming(true);
  };

  const createRecord = async () => {
    if (!session?.employee_code || !session.factory_id) {
      setFormError("当前身份已失效，请重新登录后继续。");
      return;
    }
    if (!scopedPendingSubmission && !presets) {
      setFormError("后台发布选项不可用，不能建立表单。");
      return;
    }
    let pending = scopedPendingSubmission;
    if (!pending) {
      const baseInfoPayload: Record<string, unknown> = {
        mode: baseInfo.mode,
        special_classes: baseInfo.special_classes,
        length: baseInfo.length,
        shade: baseInfo.shade,
        grade: baseInfo.grade,
        supplier: baseInfo.supplier.trim(),
        cage_no: (cageNoOverride || baseInfo.cage_no).trim(),
        bundle_count: Number(baseInfo.bundle_count),
        net_weight: netWeight?.value,
        options_version: presets!.options_version,
      };
      pending = {
        ownerEmployeeCode: session.employee_code,
        factoryId: session.factory_id,
        deviceId,
        createKey: createIdempotencyKey,
        stageKey: stageIdempotencyKey,
        draft: { ...baseInfo, special_classes: [...baseInfo.special_classes] },
        moisture: [...moisture],
        baseInfo: baseInfoPayload,
      };
      if (!writePendingSortingSubmission(pending)) {
        setFormError("浏览器无法保存本次待提交记录。为避免重复建表，尚未发送请求，请允许会话存储后重试。");
        return;
      }
      setPendingSubmission(pending);
    }
    setSaving(true);
    setFormError("");
    try {
      let created = pending.createdRecord;
      if (!created) {
        created = await mobileApiClient.createBambooRecord(
          pending.baseInfo,
          pending.createKey,
        );
        pending = { ...pending, createdRecord: created };
        writePendingSortingSubmission(pending);
        setPendingSubmission(pending);
      }
      await mobileApiClient.submitBambooStage(
        created.record_id,
        "SORT",
        {
          expected_revision: created.revision,
          device_id: pending.deviceId,
          values: { moisture: pending.moisture.filter((value) => value.trim() !== "").map(Number) },
        },
        pending.stageKey,
      );
      clearPendingSortingSubmission(pending);
      if (sortingDraftScope) clearBambooDraft(sortingDraftScope);
      setPendingSubmission(null);
      setCreating(false);
      navigate(`/mobile/records/${encodeURIComponent(created.record_id)}`);
    } catch (cause) {
      const msg = message(cause, pending.createdRecord ? "分选签字失败，可稍后继续；系统不会重复建表。" : "请求结果尚未确认，可稍后用同一请求继续。");
      setFormError(msg);
      setConfirming(false);
      // Detect duplicate cage error — allow inline edit
      if (cause instanceof MobileApiError && cause.code === "DUPLICATE_CAGE_NO") {
        setEditCageNo(true);
        setCageNoOverride("");
      }
      // Allow user to discard the stuck pending submission
      setPendingSubmission((prev) => prev ? { ...prev, lastError: msg } : prev);
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
            <button type="button" className="btn primary small" onClick={openCreateSheet} aria-label={hasPendingSubmission ? "继续未完成的分选提交" : "新建竹丝记录"}>{hasPendingSubmission ? "继续提交" : "新建"}</button>
          )}
        </div>
        <div className="section-note">{session?.factory_name || "当前工厂"} · {roleLabel(session?.bamboo_role)}</div>
      </section>

      {error && <div className="banner danger" role="alert">{error}</div>}

      {roleSupportsCageSearch && (
        <form className="bamboo-cage-search card" onSubmit={(event) => { event.preventDefault(); const value = cageQuery.trim(); if (!value) { setError("请先输入笼号。"); return; } setError(""); setSearchedCage(value); }}>
          <label htmlFor="bamboo-cage-query">{isInspector ? "按笼号查找可检测记录（可选）" : `按笼号查找${session?.bamboo_role === "DIPPING_OPERATOR" ? "上游表单" : "上游表单"}`}</label>
          <div className="btnrow"><input id="bamboo-cage-query" value={cageQuery} onChange={(event) => setCageQuery(event.target.value)} placeholder="输入完整或部分笼号" autoComplete="off" /><button type="submit" className="btn primary">搜索</button></div>
          <p>输入笼号或表号可精确查找；不搜索时显示全部可处理记录。</p>
          {searchedCage && <button type="button" className="btn secondary small" onClick={() => { setSearchedCage(""); setCageQuery(""); }}>清除"{searchedCage}"</button>}
        </form>
      )}

      <nav className="tabs" aria-label="工作分类">
        {buckets.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`tab${bucket === item.key ? " on" : ""}`}
            onClick={() => setBucket(item.key)}
          >
            {item.label}{loaded ? ` ${dashboard[item.key]}` : " —"}
          </button>
        ))}
      </nav>

      {loading ? (
        <div className="mobile-loading">加载工作中…</div>
      ) : isInspector && inspectionWindows.length === 0 && tasks.length === 0 ? (
        <div className="card empty">
          <h3>{searchedCage ? (() => { const msg = cageSearchEmptyMessage(searchedCage, bucket); if (msg) return msg.title; return "未找到匹配笼号的记录。"; })() : "当前分类暂无记录"}</h3>
          <p>{searchedCage ? cageSearchEmptyMessage(searchedCage, bucket)?.detail ?? "未找到匹配笼号的记录。" : (bucket === "available" ? "当前没有可检测的生产记录。" : bucket === "waiting" ? "生产尚未完成，没有可用的检测窗口。" : "你尚未完成任何检测记录。")}</p>
        </div>
      ) : tasks.length === 0 && inspectionWindows.length === 0 ? (
        <div className="card empty">
          <h3>{searchedCage ? `未找到笼号"${searchedCage}"的匹配记录` : "当前分类暂无记录"}</h3>
          <p>{searchedCage ? "请确认笼号是否正确，或清除搜索查看全部。" : "当前没有需要你处理的记录。上一工序完成后会自动出现在这里。"}</p>
        </div>
      ) : (
        <div className="list" aria-label="竹丝记录列表">
          {isInspector && inspectionWindows.length > 0
            ? inspectionWindows.map((window) => (
                <Link to={`/mobile/records/${encodeURIComponent(window.record_id)}`} className="record-card" key={window.record_id}>
                  <div className="record-top">
                    <div>
                      <div className="record-no">{window.display_no}</div>
                      <div className="record-meta">
                        {window.form_type === "DIPPING_DRYING" ? "浸胶+干燥联合表" : "分选表"} · 笼号 {window.cage_no || "—"}
                        <br />
                        检测窗口状态：{inspectionWindowStatusLabel(window)}
                        <br />
                        开放于 {formatTime(window.opened_at)}{window.deadline_at ? ` · 截止 ${formatTime(window.deadline_at)}` : ""}
                      </div>
                    </div>
                    <span className={`chip ${bucket === "available" ? "info" : bucket === "waiting" ? "wait" : "ok"}`}>{bucketLabel(bucket, session?.bamboo_role)}</span>
                  </div>
                  <div className="record-actions">
                    <span className="btn primary small">{bucket === "available" ? "去检测" : "查看表单"}</span>
                  </div>
                </Link>
              ))
            : tasks.map((record) => (
                <Link to={`/mobile/records/${encodeURIComponent(record.record_id)}`} className="record-card" key={record.record_id}>
                  <div className="record-top">
                    <div>
                      <div className="record-no">{record.display_no}</div>
                      <div className="record-meta">
                        {formTypeLabel(record.form_type)} · {recordState(record)}
                        <br />
                        竹笼号 {String(record.base_info.cage_no || "—")} · 等级 {String(record.base_info.grade || "—")} · 把数 {String(record.base_info.bundle_count || "—")}
                        <br />
                        当前表内状态：{stageLabel(record.current_stage)} · 更新于 {formatTime(record.updated_at)}
                      </div>
                    </div>
                    <span className={`chip ${bucket === "available" ? "info" : bucket === "waiting" ? "wait" : "ok"}`}>{bucketLabel(bucket, session?.bamboo_role)}</span>
                  </div>
                  <div className="record-actions">
                    <span className="btn primary small">{bucket === "available" ? (isInspector ? "去检测" : "去记录") : "查看表单"}</span>
                  </div>
                </Link>
              ))}
        </div>
      )}

      {createSheetVisible && (
        <div className="bamboo-v3-sheet-backdrop" role="presentation">
          <form className="bamboo-v3-bottom-sheet bamboo-v3-create-sheet" onSubmit={requestConfirm} role="dialog" aria-modal="true" aria-label="新建竹丝记录">
            <div className="bamboo-v3-sheet-handle" />
            <header><h3>{hasPendingSubmission ? "继续分选提交" : "新建竹丝工序记录"}</h3><button type="button" aria-label="关闭" disabled={saving} onClick={closeCreateSheet}>×</button></header>
            <div className="banner info">预设选项由管理员后台发布；手机端只能点选，不能临时新增。</div>
            {presetsLoading && <div className="banner info" role="status">正在加载后台发布选项…</div>}
            {presetsError && <div className="banner danger bamboo-preset-error" role="alert"><span>{presetsError}</span><button type="button" className="btn secondary small" disabled={presetsLoading || saving} onClick={() => void loadPresets()}>重新加载</button></div>}
            {hasPendingSubmission && <div className="banner info" role="status">待继续提交，字段已锁定。继续操作将使用已保存的原始数据。{formError && <button type="button" className="btn secondary small" style={{marginLeft:12}} disabled={saving} onClick={() => { clearPendingSortingSubmission(scopedPendingSubmission!); setPendingSubmission(null); setFormError(""); setPresets(null); closeCreateSheet(); }}>放弃并退出</button>}</div>}
            {formError && <div className="banner danger" role="alert">{formError}</div>}
            <div className="field-group field-group--production-method">
              <div className="field">
                <span className="field-label">作业模式</span>
                <div className="mode-toggle" aria-label="作业模式">
                  {(["分选", "分选+装笼"] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      className={`mode-btn${baseInfo.mode === mode ? " on" : ""}`}
                      aria-pressed={baseInfo.mode === mode}
                      disabled={hasPendingSubmission || saving}
                      onClick={() => setBaseInfo({ ...baseInfo, mode })}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="field-group field-group--spec-info">
              <PickerField
                label="特殊类"
                value={baseInfo.special_classes.join("、")}
                placeholder="选填，可多选（防霉、直装等）"
                required={false}
                disabled={hasPendingSubmission || !presets || presetsLoading || saving}
                onOpen={() => setPicker("special_classes")}
              />
              <PickerField label="长度（m）" value={baseInfo.length} placeholder="点开选择长度" required disabled={hasPendingSubmission || !presets || presetsLoading || saving} onOpen={() => setPicker("length")} />
              <PickerField label="深浅" value={baseInfo.shade} placeholder="点开选择深浅" required disabled={hasPendingSubmission || !presets || presetsLoading || saving} onOpen={() => setPicker("shade")} />
              <PickerField label="品级" value={baseInfo.grade} placeholder="点开选择品级" required disabled={hasPendingSubmission || !presets || presetsLoading || saving} onOpen={() => setPicker("grade")} />
            </div>
            <div className="field-group field-group--production-target">
              <label className="field">
                <span className="field-label">供应商</span>
                <input placeholder="选填，可留空" readOnly={hasPendingSubmission} value={baseInfo.supplier} onChange={(event) => setBaseInfo({ ...baseInfo, supplier: event.target.value })} />
              </label>
              <label className="field">
                <span className="field-label">笼号 <em>*</em></span>
                <input required placeholder="如：L-207" readOnly={hasPendingSubmission} value={baseInfo.cage_no} onChange={(event) => setBaseInfo({ ...baseInfo, cage_no: event.target.value })} />
              </label>
              <label className="field">
                <span className="field-label">把数 <em>*</em></span>
                <input required type="number" min="1" inputMode="numeric" readOnly={hasPendingSubmission} placeholder="本笼把数（整数）" value={baseInfo.bundle_count} onChange={(event) => setBaseInfo({ ...baseInfo, bundle_count: event.target.value })} />
              </label>
            </div>
            <div className="field-group field-group--auto-summary">
              <div className="kv">
                <span className="k">净重（自动）</span>
                {summaryNetWeight != null ? (
                  <span className="v">{summaryNetWeight} kg {netWeight && <small>（{baseInfo.bundle_count} 把 × {netWeight.factor}）</small>}</span>
                ) : (
                  <span className="v muted">填完把数和长度后自动计算</span>
                )}
              </div>
            </div>
            <div className="field-group field-group--test-data">
              <fieldset className="bamboo-moisture-fieldset bamboo-create-moisture">
                <legend>含水率检测点（%）<em>*</em></legend>
                <div className="bamboo-moisture-grid">
                  {moisture.map((value, index) => (
                    <label key={index}>
                      <span>检测点 {index + 1}</span>
                      <input
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        readOnly={hasPendingSubmission}
                        value={value}
                        placeholder="1-100"
                        onChange={(event) => setMoisture(moisture.map((item, itemIndex) => itemIndex === index ? event.target.value : item))}
                      />
                    </label>
                  ))}
                </div>
                <div className="bamboo-point-actions">
                  <button type="button" disabled={hasPendingSubmission || moisture.length >= 20} onClick={() => setMoisture([...moisture, ""])}>增加检测点</button>
                  <button type="button" disabled={hasPendingSubmission || moisture.length <= 1} onClick={() => setMoisture(moisture.slice(0, -1))}>删除最后一个</button>
                </div>
                <p className="bamboo-moisture-average">已填写 {moistureValues.length} 点 · 平均值 {moistureAverage ?? "—"}%</p>
              </fieldset>
            </div>
            <div className="field-group field-group--confirmation">
              <div className="bamboo-v3-form-actions">
                <button type="button" className="btn secondary" disabled={saving} onClick={closeCreateSheet}>{hasPendingSubmission ? "稍后继续" : "取消"}</button>
                <button type="submit" className="btn primary" disabled={saving || (!hasPendingSubmission && (presetsLoading || !presets))}>{hasPendingSubmission ? "继续提交" : "核对并提交分选/装笼记录"}</button>
              </div>
            </div>
          </form>
          {picker && presets && (
            <PickerModal
              picker={picker}
              presets={presets}
              draft={baseInfo}
              onChange={setBaseInfo}
              onClose={() => setPicker(null)}
            />
          )}
          {confirming && (
            <ConfirmCreateModal
              draft={baseInfo}
              netWeight={summaryNetWeight}
              moisture={moistureValues}
              average={moistureAverage}
              error={formError}
              recordCreated={createdRecord !== null}
              pending={hasPendingSubmission}
              saving={saving}
              editCageNo={editCageNo}
              cageNoOverride={cageNoOverride}
              onChangeCageNo={setCageNoOverride}
              onCancel={() => { setConfirming(false); setEditCageNo(false); }}
              onDefer={closeCreateSheet}
              onConfirm={() => { void createRecord(); }}
            />
          )}
        </div>
      )}
    </div>
  );
}

function PickerField({
  label,
  value,
  placeholder,
  required,
  disabled,
  onOpen,
}: {
  label: string;
  value: string;
  placeholder: string;
  required: boolean;
  disabled: boolean;
  onOpen: () => void;
}) {
  return (
    <div className="field">
      <span className="field-label">{label} {required && <em>*</em>}</span>
      <button type="button" className="picker-trigger" disabled={disabled} onClick={onOpen}>
        {value ? <span className="val">{value}</span> : <span className="ph">{placeholder}</span>}
        <span className="caret">▾ 点开选择</span>
      </button>
    </div>
  );
}

function PickerModal({
  picker,
  presets,
  draft,
  onChange,
  onClose,
}: {
  picker: PickerKey;
  presets: BambooRecordPresetOptions;
  draft: BaseInfoDraft;
  onChange: (draft: BaseInfoDraft) => void;
  onClose: () => void;
}) {
  const config = pickerConfig(picker, presets);
  const multi = picker === "special_classes";
  return (
    <div className="modal open" role="dialog" aria-modal="true" aria-label={config.title}>
      <div className="modal-sheet">
        <div className="modal-head">
          <div className="modal-title">{config.title}</div>
          <button type="button" className="modal-close" aria-label="关闭" onClick={onClose}>×</button>
        </div>
        <div className="wheel">
          {config.options.map((option) => {
            const selected = multi ? draft.special_classes.includes(option) : draft[picker] === option;
            return (
              <button
                type="button"
                key={option}
                className={`wheel-opt${selected ? " on" : ""}`}
                onClick={() => {
                  if (multi) {
                    const next = selected
                      ? draft.special_classes.filter((item) => item !== option)
                      : [...draft.special_classes, option];
                    onChange({ ...draft, special_classes: next });
                    return;
                  }
                  onChange({ ...draft, [picker]: option });
                  onClose();
                }}
              >
                {option}
              </button>
            );
          })}
        </div>
        {multi && (
          <div className="btnrow">
            <button type="button" className="btn secondary" onClick={() => onChange({ ...draft, special_classes: [] })}>清空</button>
            <button type="button" className="btn primary" onClick={onClose}>完成</button>
          </div>
        )}
      </div>
    </div>
  );
}

function ConfirmCreateModal({
  draft,
  netWeight,
  moisture,
  average,
  error,
  recordCreated,
  pending,
  saving,
  editCageNo,
  cageNoOverride,
  onChangeCageNo,
  onCancel,
  onDefer,
  onConfirm,
}: {
  draft: BaseInfoDraft;
  netWeight: number | null;
  moisture: number[];
  average: string | null;
  error: string;
  recordCreated: boolean;
  pending: boolean;
  saving: boolean;
  editCageNo: boolean;
  cageNoOverride: string;
  onChangeCageNo: (v: string) => void;
  onCancel: () => void;
  onDefer: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="modal open" role="dialog" aria-modal="true" aria-labelledby="confirmCreateTitle">
      <div className="modal-sheet">
        <div className="modal-head">
          <div className="modal-title" id="confirmCreateTitle">核对分选/装笼记录</div>
          <button type="button" className="modal-close" aria-label="关闭" onClick={pending ? onDefer : onCancel} disabled={saving}>×</button>
        </div>
        {!pending && <div className="banner info">确认后将建立分选表并绑定当前身份完成分选签字。</div>}
        {recordCreated && <div className="banner info">分选表已建立；本次重试只继续签字，不会重复创建。</div>}
        {pending && !recordCreated && <div className="banner info">上次建表请求结果尚未确认；继续会用原幂等键重放，不会换键重建。</div>}
        {error && <div className="banner danger" role="alert">{error}</div>}
        {editCageNo && !recordCreated && (
          <div className="field" style={{marginBottom:12}}>
            <span className="field-label">修改笼号后重试</span>
            <input type="text" className="field-input" value={cageNoOverride || draft.cage_no.trim()}
              onChange={(e) => onChangeCageNo(e.target.value)}
              placeholder="输入新笼号" disabled={saving} autoFocus />
          </div>
        )}
        <div className="confirm-summary">
          <b>{draft.mode}</b><br />
          {draft.grade}级 · {draft.length} m · {draft.shade} · {draft.bundle_count} 把 · 笼号 {draft.cage_no.trim()}<br />
          特殊类：{draft.special_classes.length ? draft.special_classes.join("、") : "—"}<br />
          供应商：{draft.supplier.trim() || "—"}<br />
          净重：{netWeight != null ? `${netWeight} kg` : "—"}
          <br />含水率：{moisture.join("、")}（平均 {average ?? "—"}%）
        </div>
        <div className="btnrow">
          <button type="button" className="btn secondary" onClick={pending ? onDefer : onCancel} disabled={saving}>{pending ? "稍后继续" : "返回修改"}</button>
          <button type="button" className="btn primary" onClick={onConfirm} disabled={saving}>{saving ? "提交中…" : pending ? "继续提交" : "确认提交"}</button>
        </div>
      </div>
    </div>
  );
}

function pickerConfig(picker: PickerKey, presets: BambooRecordPresetOptions): { title: string; options: string[] } {
  if (picker === "special_classes") return { title: "特殊类（可多选）", options: presets.special_classes };
  if (picker === "length") return { title: "长度（m）", options: presets.lengths };
  if (picker === "shade") return { title: "深浅", options: presets.shades };
  return { title: "品级", options: presets.grades };
}

function validateDraft(draft: BaseInfoDraft, moisture: string[]): string {
  if (!draft.length) return "请选择长度";
  if (!draft.shade) return "请选择深浅";
  if (!draft.grade) return "请选择品级";
  if (!draft.cage_no.trim()) return "请填写笼号";
  if (!/^\d+$/.test(draft.bundle_count) || Number(draft.bundle_count) <= 0) return "把数需填写正整数";
  const filled = moisture.filter((value) => value.trim() !== "");
  if (filled.length === 0) return "请至少填写一个含水率检测点";
  if (filled.some((value) => !/^\d+$/.test(value.trim()) || Number(value) < 1 || Number(value) > 100)) return "含水率需填写 1 至 100 的正整数";
  return "";
}

function workTitle(role = ""): string {
  if (role === "INSPECTOR") return "记录质量检测";
  if (role === "SUPERVISOR" || role === "PLANT_MANAGER") return "待把关记录";
  return `记录${roleStageLabel(role)}工序`;
}

function workDescription(role = ""): string {
  if (role === "INSPECTOR") return "查看当前可检测的生产记录并填写现场检测结果。";
  if (role === "SUPERVISOR" || role === "PLANT_MANAGER") return "上游完成后，本环节才可以处理";
  return "仅显示本人岗位允许填写的工序和生产对象";
}

function roleStageLabel(role = ""): string {
  return ({ SORT_OPERATOR: "分选/分选+装笼", DIPPING_OPERATOR: "浸胶", DRYING_RACK_OPERATOR: "干燥装架" } as Record<string, string>)[role] ?? "";
}

function bucketLabel(bucket: BambooTaskBucket, role = ""): string {
  if (role === "INSPECTOR") {
    return ({ available: "可检测", waiting: "等待检测条件", completed: "我的检测记录" } as Record<BambooTaskBucket, string>)[bucket];
  }
  return ({ available: "可记录", waiting: "等待上游", completed: "已完成" } as Record<BambooTaskBucket, string>)[bucket];
}

function stageLabel(stage: BambooRecord["current_stage"]): string {
  return ({ SORT: "待分选", DIPPING: "待浸胶", DRYING: "待干燥", SUPERVISOR: "待主管审核", PLANT_AUDIT: "待厂长确认" } as Record<string, string>)[stage ?? ""] ?? "流程完成";
}

function formTypeLabel(formType: BambooRecord["form_type"]): string {
  return formType === "DIPPING_DRYING" ? "浸胶+干燥联合表" : "分选表";
}

function recordState(record: BambooRecord): string {
  if (record.status === "COMPLETED") return "已生效";
  if (record.form_type === "DIPPING_DRYING" && record.current_stage === "SUPERVISOR") return "联合作业已完成";
  if (record.current_stage === "SUPERVISOR") return "分选已完成";
  return stageLabel(record.current_stage);
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

function pendingStorageKey(employeeCode: string, factoryId: string, deviceId: string): string {
  return [PENDING_SORTING_STORAGE_PREFIX, employeeCode, factoryId, deviceId]
    .map((part) => encodeURIComponent(part))
    .join(":");
}

function readPendingSortingSubmission(employeeCode: string, factoryId: string, deviceId: string): PendingSortingSubmission | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const key = pendingStorageKey(employeeCode, factoryId, deviceId);
    const raw = localStorage.getItem(key) ?? (typeof sessionStorage === "undefined" ? null : sessionStorage.getItem(key));
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<PendingSortingSubmission>;
    if (
      value.ownerEmployeeCode !== employeeCode
      || value.factoryId !== factoryId
      || value.deviceId !== deviceId
      || typeof value.createKey !== "string"
      || typeof value.stageKey !== "string"
      || !isBaseInfoDraft(value.draft)
      || !Array.isArray(value.moisture)
      || value.moisture.some((item) => typeof item !== "string")
      || !isPlainObject(value.baseInfo)
      || (value.createdRecord !== undefined && !isPlainObject(value.createdRecord))
    ) return null;
    return value as PendingSortingSubmission;
  } catch {
    return null;
  }
}

function writePendingSortingSubmission(pending: PendingSortingSubmission): boolean {
  if (typeof localStorage === "undefined") return false;
  try {
    localStorage.setItem(
      pendingStorageKey(pending.ownerEmployeeCode, pending.factoryId, pending.deviceId),
      JSON.stringify(pending),
    );
    return true;
  } catch {
    return false;
  }
}

function clearPendingSortingSubmission(pending: PendingSortingSubmission): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.removeItem(pendingStorageKey(pending.ownerEmployeeCode, pending.factoryId, pending.deviceId));
  } catch {
    // A successful server signature is authoritative even if storage cleanup is unavailable.
  }
}

function isBaseInfoDraft(value: unknown): value is BaseInfoDraft {
  if (!isPlainObject(value)) return false;
  return (value.mode === "分选" || value.mode === "分选+装笼")
    && Array.isArray(value.special_classes)
    && value.special_classes.every((item) => typeof item === "string")
    && [value.length, value.shade, value.grade, value.supplier, value.cage_no, value.bundle_count]
      .every((item) => typeof item === "string");
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function cageSearchEmptyMessage(cageNo: string, bucket: BambooTaskBucket): { title: string; detail: string } | null {
  if (!cageNo.trim()) return null;
  if (bucket === "waiting") {
    return { title: "该笼号尚未满足条件。", detail: "该笼号的上一工序尚未完成，请等待完成后刷新。" };
  }
  if (bucket === "available") {
    return { title: "未找到匹配的可用记录。", detail: `未找到笼号"${cageNo}"的可用记录。该笼号可能已完成或不存在。` };
  }
  return { title: "未找到匹配笼号的记录。", detail: `未找到笼号"${cageNo}"的相关记录。` };
}

function inspectionWindowStatusLabel(window: BambooInspectionWindow): string {
  if (window.status === "OPEN") return "待领取";
  if (window.status === "CLAIMED") return window.claimed_by ? `检测中（${window.claimed_by}）` : "检测中";
  if (window.status === "COMPLETED") return "检测完成";
  if (window.status === "EARLY_TERMINATED") return "厂长提前终止";
  if (window.status === "EXPIRED") return "检测超时";
  if (window.status === "APPEAL_CLAIMED") return "申诉填写中";
  if (window.status === "APPEAL_SUBMITTED") return "申诉待审批";
  if (window.status === "APPEAL_APPROVED") return "申诉已通过";
  if (window.status === "APPEAL_REJECTED") return "申诉已驳回";
  return window.status;
}
