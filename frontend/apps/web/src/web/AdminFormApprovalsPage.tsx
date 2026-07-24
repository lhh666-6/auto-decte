import { useCallback, useEffect, useMemo, useState } from "react";

import {
  activateManagedForm,
  decideManagedFormApproval,
  listManagedFormApprovals,
} from "./api";
import { VersionDiffPanel } from "./shared/VersionDiffPanel";
import type { DiffField } from "./shared/VersionDiffPanel";
import { ReasonConfirmDialog } from "./shared/ReasonConfirmDialog";
import type { ImpactScope, PreCheckResult } from "./shared/ReasonConfirmDialog";
import type { ManagedFormVersion } from "./types";
import "./managed-forms.css";
import "./workspace.css";

interface FactoryInfo {
  factory_id: string;
  code: string;
  name: string;
}

/* ------------------------------------------------------------------ */
/*  helpers                                                            */
/* ------------------------------------------------------------------ */

/**
 * Build a naive diff between two schema snapshots.
 * When the API returns a previous version we can diff against it.
 * For now we compare the current schema against an empty one so every
 * field shows as "added" (the version is being reviewed).
 */
function buildFieldDiff(
  _current: ManagedFormVersion,
  _previous?: ManagedFormVersion,
): { fields: DiffField[]; isFirstVersion: boolean } {
  const fields = _current.schema_json.fields ?? [];
  if (!_previous) {
    return { fields: [], isFirstVersion: true };
  }
  const prevKeys = new Set((_previous.schema_json.fields ?? []).map((f) => f.key));
  const diffFields = fields.map((f) => {
    const existed = prevKeys.has(f.key);
    const prevField = (_previous.schema_json.fields ?? []).find((pf) => pf.key === f.key);
    if (!existed) return { key: f.key, label: f.label, type: f.type, change: "added" as const };
    if (prevField && prevField.type !== f.type)
      return { key: f.key, label: f.label, type: f.type, oldValue: prevField.type, newValue: f.type, change: "modified" as const };
    return { key: f.key, label: f.label, type: f.type, change: "unchanged" as const };
  });
  return { fields: diffFields, isFirstVersion: false };
}

function buildPreCheck(item: ManagedFormVersion): PreCheckResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const fields = item.schema_json.fields ?? [];

  if (fields.length === 0) {
    warnings.push("表单版本不含任何字段");
  }
  const requiredFields = fields.filter((f) => f.required);
  if (requiredFields.length === 0) {
    warnings.push("表单没有必填字段");
  }
  const keys = fields.map((f) => f.key);
  const dupKeys = keys.filter((k, i) => keys.indexOf(k) !== i);
  if (dupKeys.length > 0) {
    errors.push(`重复字段标识: ${[...new Set(dupKeys)].join(", ")}`);
  }

  return {
    passed: errors.length === 0,
    errors,
    warnings,
  };
}

function buildImpactScope(
  item: ManagedFormVersion,
  _activatedPlants: string[],
): ImpactScope {
  return {
    factories: _activatedPlants.length > 0 ? _activatedPlants : [item.plant_id ?? "未指定"],
    affectedCount: 1,
    affectedRecords: null,
  };
}

/* ------------------------------------------------------------------ */
/*  component                                                          */
/* ------------------------------------------------------------------ */

export function AdminFormApprovalsPage() {
  const [items, setItems] = useState<ManagedFormVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [factories, setFactories] = useState<FactoryInfo[]>([]);
  const [selectedFactoryIds, setSelectedFactoryIds] = useState<Set<string>>(new Set());

  /* dialog state */
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogAction, setDialogAction] = useState<"APPROVE" | "REJECT">("APPROVE");
  const [dialogItem, setDialogItem] = useState<ManagedFormVersion | null>(null);

  /* fetch factories for selector */
  useEffect(() => {
    fetch("/api/v1/plant/factories", { credentials: "include" })
      .then(async (resp) => {
        if (resp.ok) {
          const data = (await resp.json()) as { items: FactoryInfo[] };
          setFactories(data.items ?? []);
        }
      })
      .catch(() => { /* silent */ });
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await listManagedFormApprovals();
      setItems(result.items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchItems();
  }, [fetchItems]);

  function toggleFactory(fid: string) {
    setSelectedFactoryIds((prev) => {
      const next = new Set(prev);
      if (next.has(fid)) {
        next.delete(fid);
      } else {
        next.add(fid);
      }
      return next;
    });
  }

  function openDialog(item: ManagedFormVersion, action: "APPROVE" | "REJECT") {
    setDialogItem(item);
    setDialogAction(action);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setDialogItem(null);
  }

  async function handleConfirm(_reason: string) {
    if (!dialogItem) return;
    try {
      if (dialogAction === "REJECT") {
        const updated = await decideManagedFormApproval(dialogItem.version_id, "REJECT");
        setItems((current) => current.map((value) => (
          value.version_id === updated.version_id ? updated : value
        )));
      } else {
        const updated = await decideManagedFormApproval(dialogItem.version_id, "APPROVE");
        setItems((current) => current.map((value) => (
          value.version_id === updated.version_id ? updated : value
        )));
      }
      closeDialog();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "审核失败");
      closeDialog();
    }
  }

  async function activate(item: ManagedFormVersion) {
    const plantIds = [...selectedFactoryIds];
    try {
      await activateManagedForm(item.version_id, plantIds);
      setItems((current) => current.filter((value) => value.version_id !== item.version_id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "启用失败");
    }
  }

  const dialogPreCheck = useMemo(
    () => (dialogItem ? buildPreCheck(dialogItem) : undefined),
    [dialogItem],
  );

  const dialogImpact = useMemo(
    () => (dialogItem ? buildImpactScope(dialogItem, [...selectedFactoryIds]) : undefined),
    [dialogItem, selectedFactoryIds],
  );

  /* ---------- loading / empty / error ---------- */
  if (loading) return <div role="status" className="page-loading">正在加载表单审批列表...</div>;
  if (error && items.length === 0) return <div role="alert" className="error-banner">{error}</div>;

  return (
    <section className="managed-forms-page">
      <header className="managed-page-heading">
        <div>
          <h1>表单审核与启用</h1>
          <p>审核内容版本，查看字段变更与预检结果，明确选择需要启用的工厂。</p>
        </div>
      </header>

      {error && <div role="alert" className="error-banner">{error}</div>}

      {items.length === 0 ? (
        <p className="vex-empty">当前没有待审核表单。</p>
      ) : (
        <div className="managed-form-list">
          {items.map((item) => {
            const preCheck = buildPreCheck(item);
            return (
              <article key={item.version_id} className="managed-form-card">
                <h2>{item.name}</h2>
                <p>
                  {item.form_key} · 版本 {item.version} · {item.schema_json.fields?.length ?? 0} 个字段
                </p>

                {/* version diff */}
                {(() => {
                  const { fields, isFirstVersion } = buildFieldDiff(item);
                  return (
                    <VersionDiffPanel
                      title="字段版本差异"
                      fields={fields}
                      isFirstVersion={isFirstVersion}
                      emptyMessage="无变更记录"
                    />
                  );
                })()}

                {/* pre-check result */}
                <div className={`precheck-summary ${preCheck.passed ? "precheck-passed" : "precheck-failed"}`}>
                  <strong>预检结果：{preCheck.passed ? "通过" : "未通过"}</strong>
                  {preCheck.errors.length > 0 && (
                    <ul>{preCheck.errors.map((e, i) => <li key={`pe-${i}`}>{e}</li>)}</ul>
                  )}
                  {preCheck.warnings.length > 0 && (
                    <ul>{preCheck.warnings.map((w, i) => <li key={`pw-${i}`}>{w}</li>)}</ul>
                  )}
                </div>

                {item.status === "PENDING_APPROVAL" ? (
                  <div className="managed-form-actions">
                    <button type="button" onClick={() => openDialog(item, "APPROVE")}>
                      批准版本
                    </button>
                    <button type="button" onClick={() => openDialog(item, "REJECT")}>
                      退回修改
                    </button>
                  </div>
                ) : (
                  <div className="managed-activation-panel">
                    <label className="factory-select-label">启用工厂</label>
                    {factories.length === 0 ? (
                      <p className="factory-select-empty">正在加载工厂列表...</p>
                    ) : (
                      <div className="factory-checkbox-list">
                        {factories.map((f) => (
                          <label key={f.factory_id} className="factory-checkbox-item">
                            <input
                              type="checkbox"
                              checked={selectedFactoryIds.has(f.factory_id)}
                              onChange={() => toggleFactory(f.factory_id)}
                            />
                            <span>{f.name} ({f.code})</span>
                          </label>
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => void activate(item)}
                      disabled={selectedFactoryIds.size === 0}
                    >
                      按工厂启用
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}

      {/* approval / reject dialog */}
      <ReasonConfirmDialog
        open={dialogOpen}
        title={dialogAction === "APPROVE" ? "批准表单版本" : "退回表单版本"}
        action={dialogAction}
        preCheck={dialogPreCheck}
        impactScope={dialogImpact}
        onConfirm={handleConfirm}
        onCancel={closeDialog}
      />
    </section>
  );
}
