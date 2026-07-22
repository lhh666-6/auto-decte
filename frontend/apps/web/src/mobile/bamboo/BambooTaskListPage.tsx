import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  MobileApiError,
  mobileApiClient,
  type BambooDashboard,
  type BambooRecord,
  type BambooRecordPresetOptions,
  type BambooTaskBucket,
} from "@form-detection/api-client";

import { createMobileClientId } from "../device";
import { useMobileSession } from "../session/MobileSessionProvider";

const BUCKETS: Array<{ key: BambooTaskBucket; label: string }> = [
  { key: "available", label: "可记录" },
  { key: "waiting", label: "等待上游" },
  { key: "completed", label: "已完成" },
];

const DEFAULT_PRESETS: BambooRecordPresetOptions = {
  options_version: "system-sort-v1",
  special_classes: ["直装", "防霉"],
  lengths: ["2.1", "2.3", "2.5"],
  shades: ["深", "浅"],
  grades: ["A", "B"],
  weight_factors: { "2.1": "5", "2.3": "6", "2.5": "7" },
};

type PickerKey = "special_classes" | "length" | "shade" | "grade";
type BaseInfoDraft = {
  mode: "分选" | "装笼";
  special_classes: string[];
  length: string;
  shade: string;
  grade: string;
  supplier: string;
  cage_no: string;
  bundle_count: string;
};

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
  const [bucket, setBucket] = useState<BambooTaskBucket>("available");
  const [dashboard, setDashboard] = useState<BambooDashboard>({ available: 0, waiting: 0, completed: 0 });
  const [tasks, setTasks] = useState<BambooRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [picker, setPicker] = useState<PickerKey | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [presets, setPresets] = useState<BambooRecordPresetOptions>(DEFAULT_PRESETS);
  const [baseInfo, setBaseInfo] = useState<BaseInfoDraft>(EMPTY_DRAFT);

  const netWeight = useMemo(() => {
    const bundles = Number(baseInfo.bundle_count);
    const factor = Number(presets.weight_factors[baseInfo.length]);
    if (!Number.isFinite(bundles) || bundles <= 0 || !Number.isFinite(factor)) return null;
    return { value: bundles * factor, factor };
  }, [baseInfo.bundle_count, baseInfo.length, presets.weight_factors]);

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

  const loadPresets = useCallback(async () => {
    setFormError("");
    try {
      setPresets(await mobileApiClient.getBambooRecordOptions());
    } catch (cause) {
      setPresets(DEFAULT_PRESETS);
      setFormError(message(cause, "暂时无法读取后台发布的预设，已使用系统默认选项。"));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const openCreateSheet = () => {
    setBaseInfo(EMPTY_DRAFT);
    setConfirming(false);
    setPicker(null);
    setCreating(true);
    void loadPresets();
  };

  const requestConfirm = (event: React.FormEvent) => {
    event.preventDefault();
    const validation = validateDraft(baseInfo);
    if (validation) {
      setFormError(validation);
      return;
    }
    setFormError("");
    setConfirming(true);
  };

  const createRecord = async () => {
    setSaving(true);
    setFormError("");
    try {
      const created = await mobileApiClient.createBambooRecord(
        {
          mode: baseInfo.mode,
          special_classes: baseInfo.special_classes,
          length: baseInfo.length,
          shade: baseInfo.shade,
          grade: baseInfo.grade,
          supplier: baseInfo.supplier.trim(),
          cage_no: baseInfo.cage_no.trim(),
          bundle_count: Number(baseInfo.bundle_count),
          net_weight: netWeight?.value,
          options_version: presets.options_version,
        },
        createMobileClientId("record"),
      );
      setCreating(false);
      navigate(`/mobile/records/${encodeURIComponent(created.record_id)}`);
    } catch (cause) {
      setConfirming(false);
      setFormError(message(cause, "新建记录失败，请重试。"));
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
            <button type="button" className="btn primary small" onClick={openCreateSheet} aria-label="新建竹丝记录">新建</button>
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
                    竹笼号 {String(record.base_info.cage_no || "—")} · 等级 {String(record.base_info.grade || "—")} · 把数 {String(record.base_info.bundle_count || "—")}
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
          <form className="bamboo-v3-bottom-sheet bamboo-v3-create-sheet" onSubmit={requestConfirm} role="dialog" aria-modal="true" aria-label="新建竹丝记录">
            <div className="bamboo-v3-sheet-handle" />
            <header><h3>新建竹丝工序记录</h3><button type="button" aria-label="关闭" onClick={() => setCreating(false)}>×</button></header>
            <div className="banner info">预设选项由管理员后台发布；手机端只能点选，不能临时新增。</div>
            {formError && <div className="banner danger" role="alert">{formError}</div>}
            <div className="field">
              <span className="field-label">作业模式</span>
              <div className="mode-toggle" aria-label="作业模式">
                {(["分选", "装笼"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={`mode-btn${baseInfo.mode === mode ? " on" : ""}`}
                    aria-pressed={baseInfo.mode === mode}
                    onClick={() => setBaseInfo({ ...baseInfo, mode })}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>
            <PickerField
              label="特殊类"
              value={baseInfo.special_classes.join("、")}
              placeholder="选填，可多选（防霉、直装等）"
              required={false}
              onOpen={() => setPicker("special_classes")}
            />
            <PickerField label="长度（m）" value={baseInfo.length} placeholder="点开选择长度" required onOpen={() => setPicker("length")} />
            <PickerField label="深浅" value={baseInfo.shade} placeholder="点开选择深浅" required onOpen={() => setPicker("shade")} />
            <PickerField label="品级" value={baseInfo.grade} placeholder="点开选择品级" required onOpen={() => setPicker("grade")} />
            <label className="field">
              <span className="field-label">供应商</span>
              <input placeholder="选填，可留空" value={baseInfo.supplier} onChange={(event) => setBaseInfo({ ...baseInfo, supplier: event.target.value })} />
            </label>
            <label className="field">
              <span className="field-label">笼号 <em>*</em></span>
              <input required placeholder="如：L-207" value={baseInfo.cage_no} onChange={(event) => setBaseInfo({ ...baseInfo, cage_no: event.target.value })} />
            </label>
            <label className="field">
              <span className="field-label">把数 <em>*</em></span>
              <input required type="number" min="1" inputMode="numeric" placeholder="本笼把数（整数）" value={baseInfo.bundle_count} onChange={(event) => setBaseInfo({ ...baseInfo, bundle_count: event.target.value })} />
            </label>
            <div className="kv">
              <span className="k">净重（自动）</span>
              {netWeight ? (
                <span className="v">{netWeight.value} kg <small>（{baseInfo.bundle_count} 把 × {netWeight.factor}）</small></span>
              ) : (
                <span className="v muted">填完把数和长度后自动计算</span>
              )}
            </div>
            <div className="bamboo-v3-form-actions">
              <button type="button" className="btn secondary" onClick={() => setCreating(false)}>取消</button>
              <button type="submit" className="btn primary" disabled={saving}>核对并建立</button>
            </div>
          </form>
          {picker && (
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
              netWeight={netWeight?.value ?? null}
              saving={saving}
              onCancel={() => setConfirming(false)}
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
  onOpen,
}: {
  label: string;
  value: string;
  placeholder: string;
  required: boolean;
  onOpen: () => void;
}) {
  return (
    <div className="field">
      <span className="field-label">{label} {required && <em>*</em>}</span>
      <button type="button" className="picker-trigger" onClick={onOpen}>
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
  saving,
  onCancel,
  onConfirm,
}: {
  draft: BaseInfoDraft;
  netWeight: number | null;
  saving: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="modal open" role="dialog" aria-modal="true" aria-labelledby="confirmCreateTitle">
      <div className="modal-sheet">
        <div className="modal-head">
          <div className="modal-title" id="confirmCreateTitle">确认建立竹丝记录</div>
          <button type="button" className="modal-close" aria-label="关闭" onClick={onCancel}>×</button>
        </div>
        <div className="banner info">提交前请再次核对，确认后将进入下一流程。</div>
        <div className="confirm-summary">
          <b>{draft.mode}</b><br />
          {draft.grade}级 · {draft.length} m · {draft.shade} · {draft.bundle_count} 把 · 笼号 {draft.cage_no.trim()}<br />
          特殊类：{draft.special_classes.length ? draft.special_classes.join("、") : "—"}<br />
          供应商：{draft.supplier.trim() || "—"}<br />
          净重：{netWeight != null ? `${netWeight} kg` : "—"}
        </div>
        <div className="btnrow">
          <button type="button" className="btn secondary" onClick={onCancel} disabled={saving}>返回修改</button>
          <button type="button" className="btn primary" onClick={onConfirm} disabled={saving}>{saving ? "建立中…" : "确认建立"}</button>
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

function validateDraft(draft: BaseInfoDraft): string {
  if (!draft.length) return "请选择长度";
  if (!draft.shade) return "请选择深浅";
  if (!draft.grade) return "请选择品级";
  if (!draft.cage_no.trim()) return "请填写笼号";
  if (!/^\d+$/.test(draft.bundle_count) || Number(draft.bundle_count) <= 0) return "把数需填写正整数";
  return "";
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
