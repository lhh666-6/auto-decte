import {
  TemplateApi,
  type PreflightReport,
  type TemplateField,
  type TemplateRect,
  type TemplateVersion,
} from "@form-detection/api-client";
import { useEffect, useMemo, useState } from "react";

import { FieldInspector } from "./FieldInspector_ds";
import { TemplateCanvasEditor } from "./TemplateCanvasEditor_ds";
import { TemplateLibrary } from "./TemplateLibrary_ds";
import { TemplatePreview } from "./TemplatePreview_ds";
import { businessErrorMessage } from "./ui/business-errors";
import {
  PROTECTED_PLACEMENT_MESSAGE,
  PROTECTED_ZONES,
  canEdit,
  isProtectedOverlap,
} from "./template-studio-model";
import { nextScreen, type StudioAction, type StudioScreen } from "./template-studio-state";

type Props = {
  initialScreen?: StudioScreen;
  onScreenChange?: (screen: StudioScreen) => void;
};

const INITIAL_FIELD: TemplateField = {
  field_key: "worker_name",
  display_name: "姓名",
  data_type: "text",
  input_type: "text_box",
  recognition_engine: "manual",
  minimum_prefill_confidence: 0.97,
  rules: {
    required: false,
    minimum_value: null,
    maximum_value: null,
    allowed_values: [],
    master_data_source: null,
    allow_exception_reason: false,
  },
  export_target: {
    workbook: "records.xlsx",
    worksheet: "records",
    business_column: "worker_name",
  },
  region: { x: 0.1, y: 0.2, width: 0.22, height: 0.05 },
};

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
    />
  );
}

function TemplateEditor({
  api,
  versionId,
  onBack,
}: {
  api: TemplateApi;
  versionId: string;
  onBack: () => void;
}) {
  const [version, setVersion] = useState<TemplateVersion | null>(null);
  const [report, setReport] = useState<PreflightReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedFieldKey, setSelectedFieldKey] = useState<string | null>(null);
  const [newField, setNewField] = useState<TemplateField>(INITIAL_FIELD);
  const [metadataName, setMetadataName] = useState("");
  const [metadataDescription, setMetadataDescription] = useState("");
  const [working, setWorking] = useState(false);

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
  const editable = version !== null && canEdit(version.status);

  function acceptMutation(updated: TemplateVersion, selection: string | null = selectedFieldKey) {
    setVersion(updated);
    setReport(null);
    setSelectedFieldKey(selection);
    setError(null);
  }

  async function addField() {
    if (!version) return;
    if (isProtectedOverlap(newField.region, PROTECTED_ZONES)) {
      setError(PROTECTED_PLACEMENT_MESSAGE);
      return;
    }
    setWorking(true);
    try {
      const updated = await api.addField(version.version_id, newField);
      acceptMutation(updated, newField.field_key);
      setNewField({
        ...INITIAL_FIELD,
        field_key: `field_${updated.fields.length + 1}`,
        display_name: `新字段 ${updated.fields.length + 1}`,
        export_target: {
          ...INITIAL_FIELD.export_target,
          business_column: `field_${updated.fields.length + 1}`,
        },
      });
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

  async function persistRegion(field: TemplateField, region: TemplateRect) {
    await saveField({ ...field, region });
  }

  async function deleteField(fieldKey: string) {
    if (!version) return;
    setWorking(true);
    try {
      const updated = await api.deleteField(version.version_id, fieldKey);
      acceptMutation(updated, updated.fields[0]?.field_key ?? null);
    } catch (cause) {
      setError(message(cause));
      throw cause;
    } finally {
      setWorking(false);
    }
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
        <span className={`status-pill ${version?.status === "PUBLISHED" ? "success" : "warning"}`}>{version?.status ?? "加载中"}</span>
      </header>
      {error && <div className="error-banner studio-message" role="alert">{error}</div>}
      {version ? (
        <section className="studio-grid">
          <aside className="studio-card studio-layers">
            <div><span className="eyebrow">组件与图层</span><h2>V{version.version} · {version.page.size}</h2><p className="muted">{version.fields.length} 个字段；发布终态保持只读。</p></div>
            <section className="template-metadata-editor">
              <h3>模板信息</h3>
              <label>模板名称<input value={metadataName} maxLength={100} disabled={working} onChange={(event) => setMetadataName(event.target.value)} /></label>
              <label>用途说明<textarea value={metadataDescription} maxLength={500} disabled={working} onChange={(event) => setMetadataDescription(event.target.value)} /></label>
              <button className="button button-secondary" disabled={working || !metadataName.trim() || (metadataName === version.display_name && metadataDescription === version.description)} onClick={() => void saveMetadata()}>保存模板信息</button>
            </section>
            <div className="locked-layers"><span>锁定组件</span><span>QR</span><span>SHEET</span><span>ArUco 10–13</span></div>
            <section className="layer-list" aria-label="字段图层">
              <h3>字段图层</h3>
              {version.fields.map((field) => <button key={field.field_key} type="button" className={field.field_key === selectedFieldKey ? "selected" : ""} onClick={() => setSelectedFieldKey(field.field_key)}><strong>{field.display_name}</strong><span>{field.field_key}</span></button>)}
              {version.fields.length === 0 && <p className="muted">尚未添加字段。</p>}
            </section>
            <section className="new-field-panel">
              <h3>加入新字段</h3>
              <label>字段键<input value={newField.field_key} disabled={!editable || working} onChange={(event) => setNewField({ ...newField, field_key: event.target.value })} /></label>
              <label>显示名<input value={newField.display_name} disabled={!editable || working} onChange={(event) => setNewField({ ...newField, display_name: event.target.value })} /></label>
              <label>识别引擎<select value={newField.recognition_engine} disabled={!editable || working} onChange={(event) => setNewField({ ...newField, recognition_engine: event.target.value })}><option value="manual">人工填写</option><option value="digit_template">数字格识别</option><option value="omr">OMR 勾选</option></select></label>
              <button className="button button-secondary" disabled={!editable || working} onClick={() => void addField()}>加入字段</button>
            </section>
            <div className="studio-lifecycle-actions">
              <button className="button button-secondary" disabled={!editable || working} onClick={() => void preflight()}>运行发布预检</button>
              <button className="button button-primary" disabled={version.status !== "READY_TO_PUBLISH" || working} onClick={() => void publish()}>发布模板</button>
              <button className="button button-danger-secondary" disabled={!editable || working} onClick={() => void discardDraft()}>放弃草稿</button>
            </div>
          </aside>
          <TemplateCanvasEditor
            version={version}
            selectedFieldKey={selectedFieldKey}
            editable={editable && !working}
            onSelect={setSelectedFieldKey}
            onPersist={persistRegion}
            onReject={setError}
          />
          <FieldInspector field={selectedField} editable={editable && !working} onSave={saveField} onDelete={deleteField} />
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
    </main>
  );
}

function message(cause: unknown): string {
  return businessErrorMessage(cause, "模板请求无法完成。");
}
