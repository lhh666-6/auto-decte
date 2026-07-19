import {
  TemplateApi,
  type PreflightReport,
  type TemplateField,
  type TemplateRect,
  type TemplateStaticElement,
  type TemplateVersion,
} from "@form-detection/api-client";
import { useEffect, useMemo, useRef, useState } from "react";

import { FieldInspector } from "./FieldInspector_ds";
import { GridInspector } from "./GridInspector_ds";
import { TemplateCanvasEditor } from "./TemplateCanvasEditor_ds";
import { TemplateLibrary } from "./TemplateLibrary_ds";
import { TemplatePreview } from "./TemplatePreview_ds";
import { businessErrorMessage } from "./ui/business-errors";
import { getTemplateStatusCopy } from "./ui/business-language";
import {
  PROTECTED_PLACEMENT_MESSAGE,
  PROTECTED_ZONES,
  canEdit,
  createFieldDraft,
  hasDuplicateFieldKey,
  isProtectedOverlap,
  moveRect,
  withDataType,
  withRecognitionMode,
} from "./template-studio-model";
import { nextScreen, type StudioAction, type StudioScreen } from "./template-studio-state";

type Props = {
  initialScreen?: StudioScreen;
  onScreenChange?: (screen: StudioScreen) => void;
};

type StructuralChange =
  | { kind: "add"; field: TemplateField }
  | { kind: "delete"; field: TemplateField };

type AddFieldDialogState = { internalId: string; field: TemplateField };

export function TemplateStudio({ initialScreen, onScreenChange }: Props) {
  const api = useMemo(() => new TemplateApi("/api/v1"), []);
  const [screen, setScreen] = useState<StudioScreen>(initialScreen ?? { kind: "library" });

  const initialVersionId = initialScreen && initialScreen.kind !== "library"
    ? initialScreen.versionId
    : null;
  useEffect(() => {
    setScreen(initialScreen ?? { kind: "library" });
  }, [initialScreen?.kind, initialVersionId]);

  function navigate(action: StudioAction) {
    setScreen((current) => {
      const next = nextScreen(current, action);
      onScreenChange?.(next);
      return next;
    });
  }

  async function createBlank(
    templateKey: string,
    pageSize: "A4" | "A5",
    displayName: string,
    description: string,
  ) {
    const draft = await api.createDraft(templateKey, pageSize, displayName, description);
    navigate({ type: "draftCreated", versionId: draft.version_id });
  }

  async function cloneAndOpenEditor(versionId: string) {
    const draft = await api.clone(versionId);
    navigate({ type: "cloneSucceeded", sourceVersionId: versionId, versionId: draft.version_id });
  }

  if (screen.kind === "library") {
    return (
      <TemplateLibrary
        api={api}
        onSelectPublished={(versionId) => navigate({ type: "select", versionId })}
        onOpenDraft={(versionId) => navigate({ type: "editDraft", versionId })}
        onCreateBlank={createBlank}
      />
    );
  }
  if (screen.kind === "preview") {
    return (
      <TemplatePreview
        api={api}
        versionId={screen.versionId}
        onBack={() => navigate({ type: "backToLibrary" })}
        onTune={cloneAndOpenEditor}
      />
    );
  }
  return (
    <TemplateEditor
      api={api}
      versionId={screen.versionId}
      onBack={() => navigate({ type: "backToLibrary" })}
      onClone={cloneAndOpenEditor}
    />
  );
}

function TemplateEditor({
  api,
  versionId,
  onBack,
  onClone,
}: {
  api: TemplateApi;
  versionId: string;
  onBack: () => void;
  onClone: (versionId: string) => Promise<void>;
}) {
  const [version, setVersion] = useState<TemplateVersion | null>(null);
  const [report, setReport] = useState<PreflightReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedFieldKey, setSelectedFieldKey] = useState<string | null>(null);
  const [selectedGridId, setSelectedGridId] = useState<string | null>(null);
  const [addDialog, setAddDialog] = useState<AddFieldDialogState | null>(null);
  const [structuralPast, setStructuralPast] = useState<StructuralChange[]>([]);
  const [structuralFuture, setStructuralFuture] = useState<StructuralChange[]>([]);
  const [metadataName, setMetadataName] = useState("");
  const [metadataDescription, setMetadataDescription] = useState("");
  const [working, setWorking] = useState(false);
  const addingRef = useRef(false);

  useEffect(() => {
    let active = true;
    setError(null);
    setReport(null);
    void api.getVersion(versionId)
      .then((item) => {
        if (!active) return;
        setVersion(item);
        setMetadataName(item.display_name);
        setMetadataDescription(item.description);
        setSelectedFieldKey(item.fields[0]?.field_key ?? null);
      })
      .catch((cause: unknown) => active && setError(message(cause)));
    return () => { active = false; };
  }, [api, versionId]);

  const selectedField = version?.fields.find((field) => field.field_key === selectedFieldKey) ?? null;
  const tableGrids = version?.static_elements.filter((element) => element.kind === "TABLE_GRID") ?? [];
  const selectedGrid = tableGrids.find((element) => element.element_id === selectedGridId) ?? null;
  const editable = version !== null && canEdit(version.status);

  function acceptMutation(updated: TemplateVersion, selection: string | null = selectedFieldKey) {
    setVersion(updated);
    setReport(null);
    setSelectedFieldKey(selection);
    setError(null);
  }

  function openAddDialog() {
    if (!version || !editable) return;
    setAddDialog({
      internalId: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`,
      field: createFieldDraft(version.fields.map((field) => field.field_key)),
    });
  }

  async function addField() {
    if (!version || !addDialog || addingRef.current) return;
    const field = {
      ...addDialog.field,
      field_key: addDialog.field.field_key.trim(),
      display_name: addDialog.field.display_name.trim(),
      export_target: {
        ...addDialog.field.export_target,
        business_column: addDialog.field.field_key.trim(),
      },
    };
    if (!field.field_key || !field.display_name) {
      setError("字段键和显示名不能为空。");
      return;
    }
    if (hasDuplicateFieldKey(field.field_key, version.fields)) {
      setError(`字段键“${field.field_key}”已存在，请使用唯一字段键。`);
      return;
    }
    if (isProtectedOverlap(field.region, PROTECTED_ZONES)) {
      setError(PROTECTED_PLACEMENT_MESSAGE);
      return;
    }
    const previousVersion = version;
    const previousSelection = selectedFieldKey;
    addingRef.current = true;
    setWorking(true);
    try {
      const updated = await api.addField(version.version_id, field);
      acceptMutation(updated, field.field_key);
      setStructuralPast((items) => [...items, { kind: "add", field }]);
      setStructuralFuture([]);
      setAddDialog(null);
    } catch (cause) {
      setVersion(previousVersion);
      setSelectedFieldKey(previousSelection);
      setError(message(cause));
    } finally {
      addingRef.current = false;
      setWorking(false);
    }
  }

  async function duplicateField(field: TemplateField) {
    if (!version || working) return;
    const draft = createFieldDraft(version.fields.map((item) => item.field_key));
    const copy: TemplateField = {
      ...structuredClone(field),
      field_key: draft.field_key,
      display_name: `${field.display_name} 副本`,
      export_target: { ...field.export_target, business_column: draft.field_key },
      region: moveRect(field.region, 5 / version.page.width_mm, 5 / version.page.height_mm, []),
    };
    setWorking(true);
    try {
      acceptMutation(await api.addField(version.version_id, copy), copy.field_key);
      setStructuralPast((items) => [...items, { kind: "add", field: copy }]);
      setStructuralFuture([]);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setWorking(false);
    }
  }

  async function saveField(field: TemplateField) {
    if (!version) return;
    if (isProtectedOverlap(field.region, PROTECTED_ZONES)) {
      setError(PROTECTED_PLACEMENT_MESSAGE);
      throw new Error(PROTECTED_PLACEMENT_MESSAGE);
    }
    setWorking(true);
    try {
      acceptMutation(await api.replaceField(version.version_id, field.field_key, field));
    } catch (cause) {
      setError(message(cause));
      throw cause;
    } finally {
      setWorking(false);
    }
  }

  async function saveGrid(grid: TemplateStaticElement) {
    if (!version) return;
    setWorking(true);
    try {
      acceptMutation(await api.replaceStaticElement(version.version_id, grid.element_id, grid));
      setSelectedGridId(grid.element_id);
    } catch (cause) {
      setError(message(cause));
      throw cause;
    } finally {
      setWorking(false);
    }
  }

  async function persistRegion(field: TemplateField, region: TemplateRect) {
    await saveField({ ...field, region });
  }

  async function deleteField(fieldKey: string) {
    if (!version) return;
    const deleted = version.fields.find((field) => field.field_key === fieldKey);
    if (!deleted) return;
    setWorking(true);
    try {
      const updated = await api.deleteField(version.version_id, fieldKey);
      acceptMutation(updated, updated.fields[0]?.field_key ?? null);
      setStructuralPast((items) => [...items, { kind: "delete", field: deleted }]);
      setStructuralFuture([]);
    } catch (cause) {
      setError(message(cause));
      throw cause;
    } finally {
      setWorking(false);
    }
  }

  async function applyStructuralChange(change: StructuralChange, direction: "undo" | "redo") {
    if (!version || working) return;
    const shouldAdd = (change.kind === "delete") === (direction === "undo");
    setWorking(true);
    try {
      const updated = shouldAdd
        ? await api.addField(version.version_id, change.field)
        : await api.deleteField(version.version_id, change.field.field_key);
      acceptMutation(updated, shouldAdd ? change.field.field_key : (updated.fields[0]?.field_key ?? null));
      if (direction === "undo") {
        setStructuralPast((items) => items.slice(0, -1));
        setStructuralFuture((items) => [...items, change]);
      } else {
        setStructuralFuture((items) => items.slice(0, -1));
        setStructuralPast((items) => [...items, change]);
      }
    } catch (cause) {
      setError(message(cause));
    } finally {
      setWorking(false);
    }
  }

  function undoStructuralChange() {
    const change = structuralPast.at(-1);
    if (change) void applyStructuralChange(change, "undo");
  }

  function redoStructuralChange() {
    const change = structuralFuture.at(-1);
    if (change) void applyStructuralChange(change, "redo");
  }

  async function preflight() {
    if (!version) return;
    setWorking(true);
    try {
      setError(null);
      const next = await api.preflight(version.version_id);
      setReport(next);
      setVersion((current) => current ? { ...current, status: next.status } : current);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setWorking(false);
    }
  }

  async function publish() {
    if (!version) return;
    setWorking(true);
    try {
      setError(null);
      setVersion(await api.publish(version.version_id));
    } catch (cause) {
      setError(message(cause));
    } finally {
      setWorking(false);
    }
  }

  async function saveMetadata() {
    if (!version || !metadataName.trim()) return;
    setWorking(true);
    try {
      setError(null);
      const metadata = await api.updateMetadata(
        version.template_key,
        metadataName.trim(),
        metadataDescription.trim(),
      );
      setVersion({
        ...version,
        display_name: metadata.display_name,
        description: metadata.description,
      });
      setMetadataName(metadata.display_name);
      setMetadataDescription(metadata.description);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setWorking(false);
    }
  }

  async function cloneReadOnlyVersion() {
    if (!version || editable || working) return;
    setWorking(true);
    try {
      setError(null);
      await onClone(version.version_id);
    } catch (cause) {
      setError(message(cause));
      setWorking(false);
    }
  }

  async function discardDraft() {
    if (!version || !editable) return;
    if (!window.confirm("确定放弃这个草稿吗？草稿字段和未发布修改将被永久删除。")) return;
    setWorking(true);
    try {
      setError(null);
      await api.discardDraft(version.version_id);
      onBack();
    } catch (cause) {
      setError(message(cause));
      setWorking(false);
    }
  }

  return (
    <main className="template-studio">
      <header className="studio-header">
        <button className="text-button" onClick={onBack}>返回模板库</button>
        <div><span className="eyebrow">模板可视化设计器</span><h1>{version?.display_name ?? "正在加载草稿…"}</h1><p>{version ? `${version.template_key} · ${version.description || "尚未填写用途说明"}` : "字段坐标、识别策略和发布状态均由模板 API 持久化。"}</p></div>
        <span className={`status-pill ${version?.status === "PUBLISHED" ? "success" : "warning"}`}>{version ? getTemplateStatusCopy(version.status).label : "加载中"}</span>
      </header>
      {error && <div className="error-banner studio-message" role="alert">{error}</div>}
      {version && (
        <nav className="studio-command-bar" aria-label="模板设计操作">
          <button className="button button-secondary" disabled={working || structuralPast.length === 0} onClick={undoStructuralChange}>撤销结构操作</button>
          <button className="button button-secondary" disabled={working || structuralFuture.length === 0} onClick={redoStructuralChange}>重做结构操作</button>
          {editable ? <>
            <button className="button button-secondary" disabled={working} onClick={() => void preflight()}>发布前检查</button>
            <button className="button button-primary" disabled={version.status !== "READY_TO_PUBLISH" || working} onClick={() => void publish()}>发布模板</button>
            <button className="button button-danger-secondary" disabled={working} onClick={() => void discardDraft()}>放弃草稿</button>
          </> : <button className="button button-primary" disabled={working} onClick={() => void cloneReadOnlyVersion()}>基于此版本创建新草稿</button>}
        </nav>
      )}
      {version ? (
        <section className="studio-grid">
          <aside className="studio-card studio-layers">
            <div><span className="eyebrow">模块与图层</span><h2>V{version.version} · {version.page.width_mm} × {version.page.height_mm} mm</h2><p className="muted">{version.fields.length} 个业务字段；系统定位模块不可修改。</p></div>
            <section className="module-palette" aria-label="模块">
              <h3>模块</h3>
              <button className="button button-secondary" disabled={!editable || working} onClick={openAddDialog}>＋ 添加业务字段</button>
              <div className="locked-layers"><span>系统模块</span><span>模板二维码</span><span>纸张实例码</span><span>定位标记 10–13</span></div>
            </section>
            <section className="layer-list" aria-label="字段图层">
              <h3>图层</h3>
              {version.fields.map((field) => <div className="layer-row" key={field.field_key}><button type="button" className={field.field_key === selectedFieldKey ? "selected" : ""} onClick={() => setSelectedFieldKey(field.field_key)}><strong>{field.display_name}</strong><span>{field.field_key}</span></button><button type="button" className="layer-copy" aria-label={`复制字段 ${field.display_name}`} disabled={!editable || working} onClick={() => void duplicateField(field)}>复制</button></div>)}
              {version.fields.length === 0 && <p className="muted">尚未添加字段。</p>}
            </section>
            <section className="layer-list" aria-label="明细表模块">
              <h3>明细表</h3>
              {tableGrids.map((grid) => <button type="button" className={grid.element_id === selectedGridId ? "selected" : ""} key={grid.element_id} onClick={() => { setSelectedGridId(grid.element_id); setSelectedFieldKey(null); }}><strong>{grid.text || "固定明细表"}</strong><span>{grid.rows} 行 × {grid.columns} 列</span></button>)}
              {tableGrids.length === 0 && <p className="muted">此模板没有明细表模块。</p>}
            </section>
          </aside>
          <TemplateCanvasEditor
            version={version}
            selectedFieldKey={selectedFieldKey}
            editable={editable && !working}
            onSelect={setSelectedFieldKey}
            onPersist={persistRegion}
            onReject={setError}
          />
          <div className="studio-properties">
            {selectedGrid
              ? <GridInspector grid={selectedGrid} editable={editable && !working} onSave={saveGrid} />
              : <FieldInspector field={selectedField} page={version.page} editable={editable && !working} onSave={saveField} onDelete={deleteField} />}
            <aside className="studio-card template-metadata-editor">
              <h2>模板设置</h2>
              <label>模板名称<input value={metadataName} maxLength={100} disabled={!editable || working} onChange={(event) => setMetadataName(event.target.value)} /></label>
              <label>用途说明<textarea value={metadataDescription} maxLength={500} disabled={!editable || working} onChange={(event) => setMetadataDescription(event.target.value)} /></label>
              <button className="button button-secondary" disabled={!editable || working || !metadataName.trim() || (metadataName === version.display_name && metadataDescription === version.description)} onClick={() => void saveMetadata()}>保存模板信息</button>
            </aside>
          </div>
        </section>
      ) : <section className="preview-loading">正在读取模板版本…</section>}
      <section className="studio-card preflight">
        <h2>发布预检与打印件</h2>
        {report ? (report.ok
          ? <p className="inline-success">预检通过：可以发布。</p>
          : report.issues.map((issue) => <p className="inline-warning" key={`${issue.code}-${issue.detail}`}>{issue.code}：{issue.detail}</p>))
          : <p className="muted">字段发生变化后需要重新运行预检。</p>}
        <div className="preview-artifacts">
          {version?.artifacts.map((artifact) => <a key={artifact.artifact_id} className="candidate-chip" href={artifact.download_url} target="_blank" rel="noreferrer">打开 {artifact.download_name}</a>)}
        </div>
      </section>
      {addDialog && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !working) setAddDialog(null); }}>
          <section key={addDialog.internalId} className="add-field-dialog" role="dialog" aria-modal="true" aria-labelledby="add-field-title">
            <div><span className="eyebrow">独立新增状态</span><h2 id="add-field-title">添加业务字段</h2><p className="muted">新增草稿不会读取或修改当前选中字段；创建失败时画布保持原状。</p></div>
            <label>字段键<input autoFocus value={addDialog.field.field_key} disabled={working} onChange={(event) => setAddDialog({ ...addDialog, field: { ...addDialog.field, field_key: event.target.value, export_target: { ...addDialog.field.export_target, business_column: event.target.value } } })} /></label>
            <label>显示名<input value={addDialog.field.display_name} disabled={working} onChange={(event) => setAddDialog({ ...addDialog, field: { ...addDialog.field, display_name: event.target.value } })} /></label>
            <label>数据类型<select value={addDialog.field.data_type} disabled={working} onChange={(event) => setAddDialog({ ...addDialog, field: withDataType(addDialog.field, event.target.value) })}><option value="text">文本</option><option value="integer">整数</option><option value="decimal">小数</option><option value="boolean">是/否</option></select></label>
            <label>识别方式<select value={addDialog.field.recognition_mode} disabled={working} onChange={(event) => setAddDialog({ ...addDialog, field: withRecognitionMode(addDialog.field, event.target.value as TemplateField["recognition_mode"]) })}><option value="NONE">不自动识别</option><option value="HANDWRITING_OCR">手写识别</option><option value="DIGIT_OCR">数字格识别</option><option value="PRINTED_OCR">印刷体识别</option><option value="OMR">勾选识别</option><option value="QR">二维码</option><option value="CALCULATED">计算字段</option></select></label>
            <div className="dialog-actions"><button className="button button-secondary" disabled={working} onClick={() => setAddDialog(null)}>取消</button><button className="button button-primary" disabled={working} onClick={() => void addField()}>{working ? "正在添加…" : "添加字段"}</button></div>
          </section>
        </div>
      )}
    </main>
  );
}

function message(cause: unknown): string {
  return businessErrorMessage(cause, "模板请求无法完成。");
}
