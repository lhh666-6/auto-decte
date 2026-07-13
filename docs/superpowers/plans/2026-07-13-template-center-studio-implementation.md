# Template Center Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the technical template-parameter screen with a usable template library, immutable published-template preview, and editable draft canvas.

**Architecture:** Keep `TemplateVersion` and `TemplateVersions` as the only template facts. Add list/read/clone/update/delete API endpoints over the existing SQLite template repository, then make React consume those endpoints through `TemplateApi`. Split the current monolithic `TemplateStudio_ds.tsx` into library, read-only preview, and draft editor components; only draft versions expose editing controls.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy/SQLite, Pydantic, React 18, TypeScript, Vite, Vitest.

---

## File structure

| Path | Responsibility |
|---|---|
| `app/domain/templates_ds.py` | Enforce mutable-draft field replacement/removal. |
| `app/application/template_versions_ds.py` | Template-library summaries and draft-only field mutations. |
| `app/adapters/database/template_repository_ds.py` | List template keys and read all version metadata without exposing storage URIs. |
| `app/api/routers/templates_ds.py` | Authorized template library, version read, clone and draft field endpoints. |
| `tests/unit/test_templates_domain_ds.py` | Immutable/version mutation domain tests. |
| `tests/application/test_template_versions_ds.py` | Clone and field replacement use-case tests. |
| `tests/api/test_templates_api_ds.py` | HTTP contract and permission tests. |
| `frontend/packages/api-client/src/templates_ds.ts` | Typed `GET`, `POST`, `PATCH`, `DELETE` template client. |
| `frontend/apps/web/src/template-api.test.ts` | Client method/HTTP contract tests. |
| `frontend/apps/web/src/template-studio-model.ts` | Pure selection, protected-region, and drag-to-rect helpers. |
| `frontend/apps/web/src/template-studio-model.test.ts` | Pure canvas geometry tests. |
| `frontend/apps/web/src/TemplateLibrary_ds.tsx` | First screen: cards, search/filter, empty/create/import entry points. |
| `frontend/apps/web/src/TemplatePreview_ds.tsx` | Read-only published-version preview and clone action. |
| `frontend/apps/web/src/TemplateCanvasEditor_ds.tsx` | Draft-only visual canvas and pointer interactions. |
| `frontend/apps/web/src/FieldInspector_ds.tsx` | Selected-field properties and mutation controls. |
| `frontend/apps/web/src/TemplateStudio_ds.tsx` | Feature-level state switcher; no direct fetches beyond `TemplateApi`. |
| `frontend/apps/web/src/styles.css` | Template library, preview and canvas styles following the approved visual design. |

### Task 1: Make draft field mutation explicit in the domain

**Files:**
- Modify: `app/domain/templates_ds.py`
- Test: `tests/unit/test_templates_domain_ds.py`

- [ ] **Step 1: Write failing domain tests for replacement/removal and published immutability**

```python
def test_draft_can_replace_and_remove_a_field() -> None:
    version = _draft_with_field()
    replacement = FieldDefinition(
        "quantity", "合格数量", "integer", "digit_boxes",
        Rect(0.20, 0.30, 0.24, 0.05), version.page, "digit_template", 0.97,
    )

    version.replace_field("quantity", replacement)
    version.remove_field("quantity")

    assert version.fields == []


def test_published_version_cannot_replace_or_remove_a_field() -> None:
    version = _published_with_field()
    with pytest.raises(ValueError, match="published template versions cannot be mutated"):
        version.remove_field("quantity")
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `uv run pytest tests/unit/test_templates_domain_ds.py -q`  
Expected: FAIL because `TemplateVersion` has no `replace_field` or `remove_field`.

- [ ] **Step 3: Add the two narrow domain methods**

```python
def replace_field(self, field_key: str, replacement: FieldDefinition) -> None:
    self._require_editable()
    if replacement.field_key != field_key:
        raise ValueError("replacement field_key must not change")
    if replacement.page != self.page:
        raise ValueError("field page must match template page")
    for index, field in enumerate(self.fields):
        if field.field_key == field_key:
            self.fields[index] = replacement
            self.status = TemplateStatus.DRAFT
            return
    raise KeyError(f"Unknown field: {field_key}")

def remove_field(self, field_key: str) -> None:
    self._require_editable()
    found = any(field.field_key == field_key for field in self.fields)
    if not found:
        raise KeyError(f"Unknown field: {field_key}")
    self.fields = [field for field in self.fields if field.field_key != field_key]
    self.status = TemplateStatus.DRAFT
```

Do not silently accept an unknown key.

- [ ] **Step 4: Re-run the domain test**

Run: `uv run pytest tests/unit/test_templates_domain_ds.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/domain/templates_ds.py tests/unit/test_templates_domain_ds.py
git commit -m "feat: support draft template field editing"
```

### Task 2: Add library/read/clone/mutation use cases and repository support

**Files:**
- Modify: `app/adapters/database/template_repository_ds.py`
- Modify: `app/application/template_versions_ds.py`
- Test: `tests/adapters/test_template_repository_ds.py`
- Test: `tests/application/test_template_versions_ds.py`

- [ ] **Step 1: Write failing repository and application tests**

```python
def test_repository_lists_distinct_template_keys(engine: Engine) -> None:
    repository = SqlAlchemyTemplateRepository(engine)
    repository.add_version(_version("PAYROLL_HOURLY", 1))
    repository.add_version(_version("PAYROLL_HOURLY", 2))
    repository.add_version(_version("PAYROLL_STANDARD_PIECE", 1))

    assert repository.list_template_keys() == ["PAYROLL_HOURLY", "PAYROLL_STANDARD_PIECE"]


def test_replace_field_only_changes_a_draft(repository: FakeTemplateRepository) -> None:
    service = TemplateVersions(repository)
    draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait())
    service.add_field(draft.version_id, _quantity_field(draft.page))

    updated = service.replace_field(draft.version_id, "quantity", _renamed_quantity(draft.page))

    assert updated.fields[0].display_name == "合格数量"
```

- [ ] **Step 2: Run targeted tests and verify failure**

Run: `uv run pytest tests/adapters/test_template_repository_ds.py tests/application/test_template_versions_ds.py -q`  
Expected: FAIL because the repository has no key list and the service has no replace/remove wrappers.

- [ ] **Step 3: Add narrow query and mutation methods**

Add to the repository protocol and adapter:

```python
def list_template_keys(self) -> list[str]:
    statement = select(TemplateVersionRow.template_key).distinct().order_by(TemplateVersionRow.template_key)
    with self._read_session() as session:
        return list(session.scalars(statement).all())
```

Add to `TemplateVersions`:

```python
def list_templates(self) -> list[TemplateVersion]:
    versions: list[TemplateVersion] = []
    for key in self._repository.list_template_keys():
        versions.extend(self._repository.list_versions(key))
    return versions

def replace_field(self, version_id: str, field_key: str, definition: FieldDefinition) -> TemplateVersion:
    version = self.get(version_id)
    version.replace_field(field_key, definition)
    self._repository.replace_version(version)
    return version

def remove_field(self, version_id: str, field_key: str) -> TemplateVersion:
    version = self.get(version_id)
    version.remove_field(field_key)
    self._repository.replace_version(version)
    return version
```

Make `list_templates` return full versions, ordered by `template_key`, `version`, then `version_id`; the API will group them into library cards. Preserve the existing clone rule: only `PUBLISHED` can be cloned.

- [ ] **Step 4: Run targeted tests**

Run: `uv run pytest tests/adapters/test_template_repository_ds.py tests/application/test_template_versions_ds.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/adapters/database/template_repository_ds.py app/application/template_versions_ds.py tests/adapters/test_template_repository_ds.py tests/application/test_template_versions_ds.py
git commit -m "feat: add template library and draft mutation use cases"
```

### Task 3: Publish an authorized, complete Template API contract

**Files:**
- Modify: `app/api/routers/templates_ds.py`
- Modify: `tests/api/test_templates_api_ds.py`

- [ ] **Step 1: Add failing API contract tests**

```python
def test_admin_can_list_read_clone_and_edit_a_template_draft(client: TestClient) -> None:
    published_id = _published_template(client)

    listing = client.get("/api/v1/templates", headers=_headers())
    assert listing.status_code == 200
    assert listing.json()[0]["template_key"] == "PAYROLL_HOURLY"

    preview = client.get(f"/api/v1/template-versions/{published_id}", headers=_headers())
    assert preview.json()["status"] == "PUBLISHED"

    clone = client.post(f"/api/v1/template-versions/{published_id}/clone", headers=_headers())
    draft_id = clone.json()["version_id"]
    changed = client.patch(
        f"/api/v1/template-versions/{draft_id}/fields/worker_name",
        headers=_headers(),
        json={"display_name": "填报人", "data_type": "text", "input_type": "text_box", "recognition_engine": "manual", "minimum_prefill_confidence": 1.0, "region": {"x": 0.12, "y": 0.2, "width": 0.2, "height": 0.05}},
    )
    assert changed.status_code == 200
    assert changed.json()["fields"][0]["display_name"] == "填报人"
```

Also assert that `PATCH` on the published ID returns 409 with `INVALID_LIFECYCLE`, missing versions return 404 `TEMPLATE_VERSION_NOT_FOUND`, and non-admin roles receive 403.

- [ ] **Step 2: Run the contract test and verify failure**

Run: `uv run pytest tests/api/test_templates_api_ds.py -q`  
Expected: FAIL because `GET /templates`, `GET /template-versions/{id}`, clone and `PATCH` routes do not exist.

- [ ] **Step 3: Add DTOs, routes, and complete version payloads**

Use a single `FieldRequest` Pydantic model for add and patch. Expand every API field payload to include fields needed by the editor:

```python
{
    "field_key": field.field_key,
    "display_name": field.display_name,
    "data_type": field.data_type,
    "input_type": field.input_type,
    "recognition_engine": field.recognition_engine,
    "minimum_prefill_confidence": field.minimum_prefill_confidence,
    "region": asdict(field.region),
}
```

Add routes before artifact download:

```python
@router.get("/templates")
def list_templates(
    request: Request,
    services: Services = Depends(get_services),
) -> list[dict[str, object]]:
    _require(_actor(request, services), Permission.TEMPLATE_READ)
    return [_library_item_payload(version) for version in services.templates.list_templates()]

@router.get("/template-versions/{version_id}")
def get_template_version(
    version_id: str,
    request: Request,
    services: Services = Depends(get_services),
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_READ)
    return _version_payload(services.templates.get(version_id), services.template_repository.list_artifacts(version_id))

@router.post("/template-versions/{version_id}/clone", status_code=status.HTTP_201_CREATED)
def clone_template_version(
    version_id: str,
    request: Request,
    services: Services = Depends(get_services),
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    return _version_payload(services.templates.clone(version_id), ())

@router.patch("/template-versions/{version_id}/fields/{field_key}")
def replace_field(
    version_id: str, field_key: str, body: FieldRequest, request: Request,
    services: Services = Depends(get_services),
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    return _version_payload(services.templates.replace_field(version_id, field_key, _definition(body)), ())

@router.delete("/template-versions/{version_id}/fields/{field_key}")
def delete_field(
    version_id: str, field_key: str, request: Request,
    services: Services = Depends(get_services),
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    return _version_payload(services.templates.remove_field(version_id, field_key), ())
```

Require `TEMPLATE_READ` for list/read and `TEMPLATE_CREATE_VERSION` for clone/mutations. Convert `KeyError` to 404 and `ValueError` to 409 only for immutable lifecycle violations; use 422 for invalid field payloads. Never return `internal_uri`.

- [ ] **Step 4: Run API tests**

Run: `uv run pytest tests/api/test_templates_api_ds.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/api/routers/templates_ds.py tests/api/test_templates_api_ds.py
git commit -m "feat: expose template library and draft editing api"
```

### Task 4: Extend the TypeScript API client and pure canvas model

**Files:**
- Modify: `frontend/packages/api-client/src/templates_ds.ts`
- Modify: `frontend/apps/web/src/template-api.test.ts`
- Create: `frontend/apps/web/src/template-studio-model.ts`
- Create: `frontend/apps/web/src/template-studio-model.test.ts`

- [ ] **Step 1: Write the failing client and geometry tests**

```ts
it("reads the template library with GET", async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
  await new TemplateApi("/api/v1", fetcher).listTemplates();
  expect(fetcher).toHaveBeenCalledWith("/api/v1/templates", { method: "GET", headers: {} });
});

it("clamps a dragged field inside the printable page and outside the QR zone", () => {
  expect(moveRect({ x: 0.74, y: 0.10, width: 0.20, height: 0.05 }, 0.10, 0, QR_SAFE_ZONE))
    .toEqual({ x: 0.60, y: 0.10, width: 0.20, height: 0.05 });
});
```

- [ ] **Step 2: Run the frontend tests and verify failure**

Run: `npm run test -w @form-detection/web -- template-api.test.ts template-studio-model.test.ts`  
Expected: FAIL because the methods and `moveRect` do not exist.

- [ ] **Step 3: Add typed HTTP and deterministic geometry helpers**

Define `TemplateField`, `TemplateVersion`, `TemplateLibraryItem`, and `TemplateRect` without optional editor fields. Implement a generic request method with method/body support:

```ts
listTemplates(): Promise<TemplateLibraryItem[]> {
  return this.request("/templates", { method: "GET" });
}

clone(versionId: string): Promise<TemplateVersion> {
  return this.request(`/template-versions/${encodeURIComponent(versionId)}/clone`, { method: "POST" });
}

replaceField(versionId: string, fieldKey: string, field: TemplateFieldInput): Promise<TemplateVersion> {
  return this.request(`/template-versions/${encodeURIComponent(versionId)}/fields/${encodeURIComponent(fieldKey)}`, { method: "PATCH", body: field });
}
```

In `template-studio-model.ts`, export `QR_SAFE_ZONE`, `isProtectedOverlap`, `moveRect`, and `resizeRect`. These helpers receive normalized coordinates, clamp to `[0, 1]`, and return the prior rectangle when the requested position intersects a protected region. They must not contain React code.

- [ ] **Step 4: Run the frontend tests and typecheck**

Run: `npm run test -w @form-detection/web -- template-api.test.ts template-studio-model.test.ts`  
Expected: PASS.

Run: `npm run typecheck`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/packages/api-client/src/templates_ds.ts frontend/apps/web/src/template-api.test.ts frontend/apps/web/src/template-studio-model.ts frontend/apps/web/src/template-studio-model.test.ts
git commit -m "feat: add template studio client and canvas model"
```

### Task 5: Build the library and read-only preview screens

**Files:**
- Create: `frontend/apps/web/src/TemplateLibrary_ds.tsx`
- Create: `frontend/apps/web/src/TemplatePreview_ds.tsx`
- Modify: `frontend/apps/web/src/TemplateStudio_ds.tsx`
- Modify: `frontend/apps/web/src/styles.css`

- [ ] **Step 1: Add a pure screen-state test**

Create `frontend/apps/web/src/template-studio-state.test.ts` and verify:

```ts
it("opens a published version in preview and does not create a draft", () => {
  expect(nextScreen({ kind: "library" }, { type: "select", versionId: "TPL-PUBLISHED" }))
    .toEqual({ kind: "preview", versionId: "TPL-PUBLISHED" });
});

it("moves from preview to editor only after clone success", () => {
  expect(nextScreen({ kind: "preview", versionId: "TPL-PUBLISHED" }, { type: "cloneSucceeded", versionId: "TPL-DRAFT" }))
    .toEqual({ kind: "editor", versionId: "TPL-DRAFT" });
});
```

- [ ] **Step 2: Run the screen-state test and verify failure**

Run: `npm run test -w @form-detection/web -- template-studio-state.test.ts`  
Expected: FAIL because `nextScreen` is not defined.

- [ ] **Step 3: Implement the feature-level switcher and two pages**

Replace the current direct-create view with:

```tsx
type StudioScreen =
  | { kind: "library" }
  | { kind: "preview"; versionId: string }
  | { kind: "editor"; versionId: string };

return screen.kind === "library" ? <TemplateLibrary onSelect={openPreview} onCreateBlank={createBlank} />
  : screen.kind === "preview" ? <TemplatePreview versionId={screen.versionId} onTune={cloneAndOpenEditor} onBack={openLibrary} />
  : <TemplateCanvasEditor versionId={screen.versionId} onBack={openLibrary} />;
```

`TemplateLibrary` loads `listTemplates()` on mount, supports client-side text search and status/category chips, and renders the four documented payroll template cards when the API returns them. It renders an honest empty state if the database has no templates; it must not fabricate published versions. `TemplatePreview` loads a version with `getVersion()`, renders its page and field list read-only, and invokes `clone()` only when the user clicks “基于此模板调优”.

Create clear actions for “创建空白模板” and “导入模板包”; the latter is visually present but disabled with the exact label “模板包导入将在安全 ZIP 导入 API 完成后开放”, because this API is outside the approved implementation scope.

- [ ] **Step 4: Add styles and perform visual acceptance**

Use the approved hierarchy: 220–260px library rail, dense template cards, a full paper-ratio preview, and an action inspector. Remove the large empty three-column parameter page. Run:

```powershell
npm run build:web
npm run dev:web
```

Open `http://127.0.0.1:5175/`, then verify manually:

1. Template navigation opens the library first.
2. Selecting a published card never modifies it.
3. “基于此模板调优” creates a draft and changes the visible status to `DRAFT`.

- [ ] **Step 5: Run tests and commit**

Run: `npm run test -w @form-detection/web -- template-studio-state.test.ts template-api.test.ts`  
Expected: PASS.

```powershell
git add frontend/apps/web/src/TemplateLibrary_ds.tsx frontend/apps/web/src/TemplatePreview_ds.tsx frontend/apps/web/src/TemplateStudio_ds.tsx frontend/apps/web/src/template-studio-state.ts frontend/apps/web/src/template-studio-state.test.ts frontend/apps/web/src/styles.css
git commit -m "feat: add template library and read-only preview"
```

### Task 6: Implement the editable draft canvas and field inspector

**Files:**
- Create: `frontend/apps/web/src/TemplateCanvasEditor_ds.tsx`
- Create: `frontend/apps/web/src/FieldInspector_ds.tsx`
- Modify: `frontend/apps/web/src/TemplateStudio_ds.tsx`
- Modify: `frontend/apps/web/src/styles.css`
- Test: `frontend/apps/web/src/template-studio-model.test.ts`

- [ ] **Step 1: Add failing interaction-model tests**

```ts
it("keeps a published preview read-only", () => {
  expect(canEdit("PUBLISHED")).toBe(false);
});

it("allows a draft field move that does not enter protected zones", () => {
  expect(moveRect({ x: 0.12, y: 0.22, width: 0.2, height: 0.05 }, 0.03, 0.01, QR_SAFE_ZONE))
    .toEqual({ x: 0.15, y: 0.23, width: 0.2, height: 0.05 });
});
```

- [ ] **Step 2: Run the model tests and verify failure**

Run: `npm run test -w @form-detection/web -- template-studio-model.test.ts`  
Expected: FAIL because `canEdit` does not exist.

- [ ] **Step 3: Implement canvas and inspector without hidden mutations**

`TemplateCanvasEditor` must load the draft version, map normalized regions to CSS percentages, and render a `<button>` overlay for each field. Pointer drag calls `moveRect`; on pointer-up it invokes `replaceField` with the full selected field definition and the new region. If `isProtectedOverlap` returns true, leave the server state unchanged and show “该位置属于二维码、实例码、定位标记或打印安全区，不能放置字段”。

`FieldInspector` must receive the selected `TemplateField` and callbacks as props. It updates only on an explicit “保存字段” action:

```tsx
<button type="button" onClick={() => onSave({ ...draft, region: selected.region })}>
  保存字段
</button>
```

It exposes display name, data type, input type, recognition engine, prefill threshold, and normalized x/y/width/height. It shows delete only for a draft and requires a browser confirmation before calling `deleteField`.

- [ ] **Step 4: Connect preflight/publish and test visually**

Keep preflight and publish through `TemplateApi`. After any field mutation, clear a stale preflight report and show `DRAFT`; after `preflight()` use the API response status; only expose publish when `READY_TO_PUBLISH`.

Run: `npm run build:web`  
Expected: PASS.

Manual browser check:

1. Select a field, change its label, save, reload, and confirm persistence.
2. Drag a field inside the page and confirm its rectangle persists.
3. Drag a field into QR safe zone and confirm the field stays at its prior position.
4. Confirm a published preview has no editable inputs or delete button.

- [ ] **Step 5: Run targeted tests and commit**

Run: `npm run test -w @form-detection/web -- template-studio-model.test.ts template-api.test.ts`  
Expected: PASS.

```powershell
git add frontend/apps/web/src/TemplateCanvasEditor_ds.tsx frontend/apps/web/src/FieldInspector_ds.tsx frontend/apps/web/src/TemplateStudio_ds.tsx frontend/apps/web/src/template-studio-model.ts frontend/apps/web/src/template-studio-model.test.ts frontend/apps/web/src/styles.css
git commit -m "feat: add editable template draft canvas"
```

### Task 7: Full validation, progress update, and handoff

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Run full backend and frontend verification**

Run:

```powershell
uv run python -m pytest -q
uv run python -m ruff check .
uv run python -m mypy app config
Set-Location frontend
npm run test
npm run build:web
```

Expected: every command exits with code 0.

- [ ] **Step 2: Perform lifecycle browser acceptance**

Verify the entire visible path using a local admin identity: template library → published preview → clone draft → add/edit/move/delete a field → preflight → publish → open generated PNG/PDF. Verify an existing imported form remains bound to its original template version.

- [ ] **Step 3: Record only verified outcomes**

Append a dated `PROGRESS.md` section that states the commit IDs, exact verification outputs, the completed template-center capabilities, and any intentionally unimplemented template-package import capability. Do not claim dynamic rows, multi-page templates, or a desktop shell.

- [ ] **Step 4: Commit and push**

```powershell
git add PROGRESS.md
git commit -m "docs: record template studio completion"
git push origin modular-architecture
```

## Plan self-review

- Spec coverage: Tasks 1–3 enforce immutable versions and provide the required API; Tasks 4–6 implement the template library, read-only preview, protected visual editor and field persistence; Task 7 verifies and records the delivery.
- Scope: ZIP template-package import, multi-page layouts and dynamic rows remain explicitly out of implementation scope; their UI is an honest unavailable action, not a fake workflow.
- Naming: `TemplateField`, `TemplateVersion`, `replaceField`, `moveRect`, `QR_SAFE_ZONE` and `TemplateCanvasEditor` are introduced consistently before use.
