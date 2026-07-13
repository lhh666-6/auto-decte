import { TemplateApi, type TemplateVersion } from "@form-detection/api-client";
import { useEffect, useMemo, useState } from "react";

import { TemplateLibrary } from "./TemplateLibrary_ds";
import { TemplatePreview } from "./TemplatePreview_ds";
import { nextScreen, type StudioAction, type StudioScreen } from "./template-studio-state";

type Props = { onBack: () => void };

export function TemplateStudio({ onBack }: Props) {
  const api = useMemo(() => new TemplateApi("/api/v1"), []);
  const [screen, setScreen] = useState<StudioScreen>({ kind: "library" });

  function navigate(action: StudioAction) { setScreen((current) => nextScreen(current, action)); }
  async function createBlank(templateKey: string, pageSize: "A4" | "A5") {
    const draft = await api.createDraft(templateKey, pageSize);
    navigate({ type: "draftCreated", versionId: draft.version_id });
  }
  async function cloneAndOpenEditor(versionId: string) {
    const draft = await api.clone(versionId);
    navigate({ type: "cloneSucceeded", versionId: draft.version_id });
  }

  if (screen.kind === "library") return <TemplateLibrary api={api} onBack={onBack} onSelectPublished={(versionId) => navigate({ type: "select", versionId })} onOpenDraft={(versionId) => navigate({ type: "editDraft", versionId })} onCreateBlank={createBlank} />;
  if (screen.kind === "preview") return <TemplatePreview api={api} versionId={screen.versionId} onBack={() => navigate({ type: "backToLibrary" })} onTune={cloneAndOpenEditor} />;
  return <TemplateEditorNextTask api={api} versionId={screen.versionId} onBack={() => navigate({ type: "backToLibrary" })} />;
}

function TemplateEditorNextTask({ api, versionId, onBack }: { api: TemplateApi; versionId: string; onBack: () => void }) {
  const [version, setVersion] = useState<TemplateVersion | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void api.getVersion(versionId).then((item) => active && setVersion(item)).catch((cause: unknown) => active && setError(cause instanceof Error ? cause.message : "无法读取草稿。"));
    return () => { active = false; };
  }, [api, versionId]);

  return <main className="template-center editor-next-task">
    <header className="template-center-header"><div><button className="text-button" onClick={onBack}>返回模板库</button><span className="eyebrow">草稿版本</span><h1>{version?.template_key ?? "正在加载草稿…"}</h1><p>草稿编辑器将在下一任务完成；当前版本已安全创建，可随时返回模板库。</p></div><span className="status-pill warning">{version?.status ?? "草稿"}</span></header>
    {error && <div className="error-banner">{error}</div>}
    {version && <section className="editor-handoff-card"><h2>V{version.version} 草稿已就绪</h2><p>页面：{version.page.size} · {version.page.orientation === "portrait" ? "纵向" : version.page.orientation}；已继承 {version.fields.length} 个字段。</p><p className="muted">下一任务将提供画布编辑、字段属性、预检与发布操作。</p></section>}
  </main>;
}
