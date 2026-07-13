# Template Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a persisted, immutable, printable template-version foundation that turns the existing payroll forms into safely published paper-form templates.

**Architecture:** Keep template authoring in the `templates` module.  Framework-independent template entities validate identity, geometry, field declarations and lifecycle; an application service owns draft, preflight, publish and clone transitions; SQLite persists versions, fields and generated artifacts.  The React Template Studio calls only `/api/v1/templates` and never accesses storage paths or Tauri/browser-file APIs directly.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, OpenCV QR encoder, Pillow PDF/PNG encoder, SQLite, React 18, Vite, TypeScript, Vitest.

---

## Locked Phase-A scope

- First-class template, version, field and printable-artifact records.
- Immutable publication, clone-to-tune, IFD template QR, `SHEET` instance identity generation, A4/A5 canonical coordinate declarations, corner-marker safe zones and publish preflight.
- Safe template package **export** and manifest verification.  ZIP **import** and image ingestion remain Phase B, because the current API has no controlled upload endpoint yet.
- A usable Template Studio: list versions, create a draft, add a fixed rectangular field, run preflight, publish and open the generated print artifact.
- Four seed definitions derived from the supplied historical payroll sheets: hourly assessment, standard piece rate, fixed production grid and equipment/process piece rate.  They are templates, not imports of historical payroll records.

## File structure

| File | Responsibility |
|---|---|
| `app/domain/templates_ds.py` | Immutable template entities, lifecycle enums, geometry and QR/checksum functions. |
| `app/application/template_versions_ds.py` | Draft, field, preflight, publish, clone and package use cases plus ports. |
| `app/adapters/database/models.py` | ORM rows for template versions, template fields and template artifacts. |
| `app/adapters/database/template_repository_ds.py` | SQLAlchemy adapter implementing the template ports. |
| `alembic/versions/002_template_versions_ds.py` | Upgrade from revision `001` without changing historic form rows. |
| `app/adapters/templates/print_renderer_ds.py` | Deterministic QR/corner-marker PNG/PDF rendering and SHA-256 artifacts. |
| `app/services/container.py` | Compose one template repository/service/renderer into `Services`. |
| `app/api/routers/templates_ds.py` | Authorized, path-safe template API. |
| `app/api/main_ds.py` | Register the template router. |
| `frontend/packages/api-client/src/templates_ds.ts` | Typed client for template endpoints. |
| `frontend/apps/web/src/TemplateStudio_ds.tsx` | Interactive template list and draft/publish screen. |
| `frontend/apps/web/src/App.tsx` | Route the existing “模板与字段” navigation to the studio. |
| `docs/design/legacy-payroll-template-inventory.md` | Evidence-based mapping from the nine supplied files to the four seed template families. |

### Task 1: Domain contracts and identity checks

**Files:**
- Create: `app/domain/templates_ds.py`
- Create: `tests/templates/test_template_domain_ds.py`

- [ ] **Step 1: Write the failing domain tests**

```python
from app.domain.templates_ds import (
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateStatus,
    build_sheet_payload,
    build_template_payload,
)


def test_template_payload_is_deterministic_and_checksums_key_and_version() -> None:
    assert build_template_payload("PAYROLL_HOURLY", 3) == "IFD|PAYROLL_HOURLY|3|9A8B"


def test_invalid_template_key_and_out_of_canvas_field_are_rejected() -> None:
    page = PageSpec.a4_portrait()
    with pytest.raises(ValueError, match="template_key"):
        build_template_payload("hourly-pay", 1)
    with pytest.raises(ValueError, match="inside canonical canvas"):
        FieldDefinition("hours", "工时", "decimal", "digit_boxes", Rect(0.9, 0.2, 0.2, 0.1), page)


def test_published_version_cannot_be_mutated() -> None:
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    version.publish()
    assert version.status is TemplateStatus.PUBLISHED
    with pytest.raises(ValueError, match="published"):
        version.add_field(FieldDefinition("hours", "工时", "decimal", "digit_boxes", Rect(0.1, 0.1, 0.1, 0.1), version.page))
```

- [ ] **Step 2: Run the domain tests and verify they fail**

Run: `pytest tests/templates/test_template_domain_ds.py -q`

Expected: `ModuleNotFoundError: No module named 'app.domain.templates_ds'`.

- [ ] **Step 3: Implement the smallest framework-free contract**

```python
class TemplateStatus(StrEnum):
    DRAFT = "DRAFT"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    READY_TO_PUBLISH = "READY_TO_PUBLISH"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


def build_template_payload(template_key: str, version: int) -> str:
    _validate_template_key(template_key)
    if version < 1:
        raise ValueError("version must be a positive integer")
    body = f"{template_key}|{version}".encode("ascii")
    return f"IFD|{template_key}|{version}|{zlib.crc32(body) & 0xFFFF:04X}"
```

Define `Rect` with normalized values in `[0, 1]`, `PageSpec.a4_portrait()` with the approved 2480×3508 canonical canvas, `FieldDefinition`, `TemplateVersion` and `build_sheet_payload`.  `TemplateVersion.add_field()` must reject duplicate `field_key` values and any mutation unless status is `DRAFT`.

- [ ] **Step 4: Correct the checksum test to the computed stable value and run it**

Run: `pytest tests/templates/test_template_domain_ds.py -q`

Expected: all tests pass.  Replace `9A8B` in the test with the exact four-character value generated by the adopted CRC32-low-16 algorithm; do not hard-code a value discovered from a different checksum algorithm.

- [ ] **Step 5: Commit the domain contract**

```bash
git add app/domain/templates_ds.py tests/templates/test_template_domain_ds.py
git commit -m "feat: add template domain contracts"
```

### Task 2: Persist template versions without altering historic forms

**Files:**
- Modify: `app/adapters/database/models.py`
- Create: `app/adapters/database/template_repository_ds.py`
- Create: `alembic/versions/002_template_versions_ds.py`
- Create: `tests/adapters/test_template_repository_ds.py`

- [ ] **Step 1: Write failing persistence tests**

```python
def test_repository_round_trips_fields_and_artifact_without_storage_path(tmp_path: Path) -> None:
    repository = SqlAlchemyTemplateRepository(create_sqlite_engine(tmp_path / "template.db"))
    version = sample_draft()
    repository.add_version(version)
    repository.add_artifact(TemplateArtifact("ART-1", version.version_id, "PRINT_PDF", "ART-1.pdf", "a" * 64))
    loaded = repository.get_version(version.version_id)
    assert loaded is not None
    assert [field.field_key for field in loaded.fields] == ["worker_name", "hours"]
    assert repository.list_artifacts(version.version_id)[0].download_name == "ART-1.pdf"
```

- [ ] **Step 2: Run and verify the persistence test fails**

Run: `pytest tests/adapters/test_template_repository_ds.py -q`

Expected: import failure for `SqlAlchemyTemplateRepository`.

- [ ] **Step 3: Add the migration and ORM rows**

Create `template_versions` keyed by `version_id`, with unique `(template_key, version)`, status, page JSON, parent version, manifest hash, creator and timestamps.  Create `template_fields` keyed by `field_id`, FK to version, unique `(version_id, field_key)`, and JSON `definition`.  Create `template_artifacts` keyed by `artifact_id`, FK to version, artifact kind, safe download name, SHA-256 and internal URI.  The response DTO must never expose `internal_uri`.

```python
class TemplateVersionRow(Base):
    __tablename__ = "template_versions"
    __table_args__ = (UniqueConstraint("template_key", "version"),)
    version_id: Mapped[str] = mapped_column(String, primary_key=True)
    template_key: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    page: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
```

Set `down_revision = "001"`; update `HEAD_REVISION` to `"002"` in `app/infrastructure/database/migrations.py`.

- [ ] **Step 4: Implement the repository and run the test**

Run: `pytest tests/adapters/test_template_repository_ds.py -q`

Expected: pass, including restart/round-trip behavior.

- [ ] **Step 5: Commit the persistence boundary**

```bash
git add app/adapters/database/models.py app/adapters/database/template_repository_ds.py \
  app/infrastructure/database/migrations.py alembic/versions/002_template_versions_ds.py \
  tests/adapters/test_template_repository_ds.py
git commit -m "feat: persist template versions"
```

### Task 3: Preflight, publication, cloning and package manifest

**Files:**
- Create: `app/application/template_versions_ds.py`
- Create: `tests/application/test_template_versions_ds.py`

- [ ] **Step 1: Write failing use-case tests**

```python
def test_preflight_rejects_missing_corner_markers_and_overlapping_qr_safe_zone() -> None:
    service = TemplateVersions(repository, renderer)
    draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait(), actor_id="ADMIN")
    service.add_field(draft.version_id, field_at_qr_safe_zone(), actor_id="ADMIN")
    report = service.preflight(draft.version_id, actor_id="ADMIN")
    assert report.ok is False
    assert {issue.code for issue in report.issues} >= {"QR_SAFE_ZONE_OVERLAP", "MISSING_CORNER_MARKER"}


def test_publish_writes_hash_manifest_and_refuses_second_publish() -> None:
    ready = service_with_complete_layout().preflight_and_ready()
    published = ready.publish(actor_id="ADMIN")
    assert published.status.value == "PUBLISHED"
    assert published.manifest_sha256 is not None
    with pytest.raises(ValueError, match="published"):
        ready.publish(actor_id="ADMIN")
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/application/test_template_versions_ds.py -q`

Expected: import failure for `TemplateVersions`.

- [ ] **Step 3: Implement explicit preflight rules**

Implement `create_draft`, `add_field`, `preflight`, `publish`, `clone` and `build_package_manifest`.  Preflight must report every problem, not only the first: valid uppercase `template_key`; positive version; unique field keys; in-page regions; no overlap with template QR, optional sheet QR, 10/11/12/13 marker safety zones or print edge; QR/corner declaration present; engine/data-type compatibility; unique export keys.  Publishing must require `READY_TO_PUBLISH`, create `IFD|…` payload, compute SHA-256 for each generated package member, persist status and write an audit event.

```python
def clone(self, version_id: str, actor_id: str) -> TemplateVersion:
    source = self._require(version_id)
    if source.status is not TemplateStatus.PUBLISHED:
        raise ValueError("only published versions can be cloned")
    return self.create_draft(source.template_key, source.page, actor_id, parent_version_id=source.version_id)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/application/test_template_versions_ds.py -q`

Expected: pass.

- [ ] **Step 5: Commit publication logic**

```bash
git add app/application/template_versions_ds.py tests/application/test_template_versions_ds.py
git commit -m "feat: add template publication preflight"
```

### Task 4: Generate printable PNG/PDF artifacts and paper-instance IDs

**Files:**
- Create: `app/adapters/templates/print_renderer_ds.py`
- Create: `tests/adapters/test_template_print_renderer_ds.py`

- [ ] **Step 1: Write failing renderer tests**

```python
def test_renderer_generates_png_and_pdf_with_template_payload_and_four_markers(tmp_path: Path) -> None:
    renderer = TemplatePrintRenderer(tmp_path)
    artifacts = renderer.render(sample_published_template(), print_batch="PB20260713A", sequence=128)
    assert {artifact.kind for artifact in artifacts} == {"PRINT_PNG", "PRINT_PDF"}
    assert all(Path(artifact.internal_uri).is_file() for artifact in artifacts)
    assert renderer.sheet_payload("PB20260713A", 128).startswith("SHEET|PB20260713A|000128|")
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/adapters/test_template_print_renderer_ds.py -q`

Expected: import failure for `TemplatePrintRenderer`.

- [ ] **Step 3: Implement deterministic print rendering**

Use `cv2.QRCodeEncoder_create()` to generate the QR image and Pillow to assemble the canonical A4/A5 canvas.  Draw the four declared marker ID labels and black-square marker placeholders in the safe zones; do not claim ArUco detection is implemented until Phase B.  Render the QR payload at publication and optional `SHEET` payload at print-batch generation.  Save a 300-DPI PNG and use `Image.save(..., "PDF", resolution=300.0)` for PDF.  Artifact storage must be beneath the configured evidence root and return an opaque ID plus safe download name.

- [ ] **Step 4: Run renderer tests**

Run: `pytest tests/adapters/test_template_print_renderer_ds.py -q`

Expected: pass; inspect the generated PNG with the local image viewer once before claiming visual success.

- [ ] **Step 5: Commit printable artifacts**

```bash
git add app/adapters/templates/print_renderer_ds.py tests/adapters/test_template_print_renderer_ds.py
git commit -m "feat: render printable template artifacts"
```

### Task 5: Expose a secure Template API

**Files:**
- Create: `app/api/routers/templates_ds.py`
- Modify: `app/services/container.py`
- Modify: `app/api/main_ds.py`
- Create: `tests/api/test_templates_api_ds.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_admin_can_create_preflight_publish_and_download_template_artifact(client: TestClient) -> None:
    created = client.post("/api/v1/templates", json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"})
    assert created.status_code == 201
    version_id = created.json()["version_id"]
    assert client.post(f"/api/v1/template-versions/{version_id}/preflight").status_code == 200
    assert client.post(f"/api/v1/template-versions/{version_id}/publish").status_code == 409


def test_template_response_does_not_expose_storage_uri(client: TestClient) -> None:
    payload = client.get("/api/v1/templates").json()
    assert "internal_uri" not in repr(payload)
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/api/test_templates_api_ds.py -q`

Expected: 404 because the templates router is not registered.

- [ ] **Step 3: Add the API and authorization checks**

Register `GET/POST /api/v1/templates`, `GET /api/v1/template-versions/{version_id}`, `POST /fields`, `POST /preflight`, `POST /publish`, `POST /clone`, `POST /print-batches`, `GET /artifacts/{artifact_id}/content`, and `GET /package`.  Use the existing current-identity dependency and `templates.*` permissions.  Artifact content must stream only a repository-selected safe file; never accept a client path or URI.  Return `409` for invalid lifecycle transitions and `422` for malformed geometry.

- [ ] **Step 4: Run API tests**

Run: `pytest tests/api/test_templates_api_ds.py -q`

Expected: pass.

- [ ] **Step 5: Commit Template API**

```bash
git add app/api/routers/templates_ds.py app/api/main_ds.py app/services/container.py tests/api/test_templates_api_ds.py
git commit -m "feat: expose template management api"
```

### Task 6: Make the Template Studio a real React feature

**Files:**
- Create: `frontend/packages/api-client/src/templates_ds.ts`
- Modify: `frontend/packages/api-client/src/index_ds.ts`
- Create: `frontend/apps/web/src/TemplateStudio_ds.tsx`
- Modify: `frontend/apps/web/src/App.tsx`
- Create: `frontend/apps/web/src/TemplateStudio_ds.test.tsx`

- [ ] **Step 1: Write a failing component test**

```tsx
it("creates a draft and displays preflight issues before publish", async () => {
  render(<TemplateStudio api={fakeApi} />);
  await userEvent.type(screen.getByLabelText("模板键"), "PAYROLL_HOURLY");
  await userEvent.click(screen.getByRole("button", { name: "创建草稿" }));
  await userEvent.click(screen.getByRole("button", { name: "运行发布预检" }));
  expect(await screen.findByText("缺少字段定义")).toBeVisible();
});
```

- [ ] **Step 2: Run and verify failure**

Run: `npm run test --workspace @form-detection/web -- TemplateStudio_ds.test.tsx`

Expected: module/component not found.

- [ ] **Step 3: Implement the feature through the API client**

Implement a two-pane screen that preserves the approved navy/teal workbench style: left list (key, version, status) and right A4/A5 canvas.  Add a labeled form for key/page, a field editor for stable `field_key`, label, data type, input type and normalized rectangle, visible red safety zones, preflight issue list, publish action and “打开打印件” link.  In `App.tsx`, make the existing “模板与字段” button change the active feature instead of being a dead button.  No direct `fetch`, file-picker, Tauri or local-path calls outside the typed API client/ports.

- [ ] **Step 4: Run component tests and typecheck**

Run: `npm run test --workspace @form-detection/web -- TemplateStudio_ds.test.tsx && npm run typecheck`

Expected: tests and TypeScript pass.

- [ ] **Step 5: Commit the studio**

```bash
git add frontend/packages/api-client/src/templates_ds.ts frontend/packages/api-client/src/index_ds.ts \
  frontend/apps/web/src/TemplateStudio_ds.tsx frontend/apps/web/src/TemplateStudio_ds.test.tsx \
  frontend/apps/web/src/App.tsx
git commit -m "feat: add template studio"
```

### Task 7: Create the four reviewed seed-template definitions

**Files:**
- Create: `app/modules/templates/seed_templates_ds.py`
- Create: `tests/modules/test_seed_templates_ds.py`
- Create: `docs/design/legacy-payroll-template-inventory.md`

- [ ] **Step 1: Write failing seed tests**

```python
def test_seed_templates_cover_each_historical_form_family() -> None:
    keys = {template.template_key for template in legacy_payroll_seed_templates()}
    assert keys == {
        "PAYROLL_HOURLY",
        "PAYROLL_STANDARD_PIECE",
        "PAYROLL_FIXED_PRODUCTION_GRID",
        "PAYROLL_EQUIPMENT_PROCESS",
    }
    assert all(template.status is TemplateStatus.DRAFT for template in legacy_payroll_seed_templates())
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/modules/test_seed_templates_ds.py -q`

Expected: import failure for `legacy_payroll_seed_templates`.

- [ ] **Step 3: Implement definitions and the legacy inventory**

Define the four drafts with only fixed regions and fields supported by Phase A.  Include common fields `work_date`, `shift`, `worker_name`, `remarks`, `assessment_result`; add fixed line keys (`line_01` through `line_10`) rather than dynamic rows.  The inventory must record this factual mapping:

| Seed key | Historical source files |
|---|---|
| `PAYROLL_HOURLY` | `计时工日工资计算表.xls`, `叉车工日工资计算表.xls` |
| `PAYROLL_STANDARD_PIECE` | `炭化、油炉人员日工资计算表.xls` (炭化), `竹丝装架日工资计算表.xls`, `装架组工资计算表.xls`, `蒸煮单价表.xlsx`, `碳化单价表.xlsx` |
| `PAYROLL_FIXED_PRODUCTION_GRID` | `热压岗位日工资计算表.xls`, `开片组日工资计算表.xls` |
| `PAYROLL_EQUIPMENT_PROCESS` | `炭化、油炉人员日工资计算表.xls` (油炉/热压工作表) |

State explicitly that the current analysis found no formulas in the operational form sheets, and that the original `.xls` files remain untouched.  Do not copy wages, names or historical records into seed data.

- [ ] **Step 4: Run seed tests**

Run: `pytest tests/modules/test_seed_templates_ds.py -q`

Expected: pass.

- [ ] **Step 5: Commit mappings**

```bash
git add app/modules/templates/seed_templates_ds.py tests/modules/test_seed_templates_ds.py \
  docs/design/legacy-payroll-template-inventory.md
git commit -m "docs: map legacy payroll forms to template seeds"
```

### Task 8: Verify, document the known boundary and publish the phase

**Files:**
- Modify: `PROGRESS.md`
- Modify: `docs/CODEX_HANDOFF.md`

- [ ] **Step 1: Run focused backend checks**

Run: `pytest tests/templates tests/adapters/test_template_repository_ds.py tests/application/test_template_versions_ds.py tests/adapters/test_template_print_renderer_ds.py tests/api/test_templates_api_ds.py tests/modules/test_seed_templates_ds.py -q`

Expected: all listed tests pass.

- [ ] **Step 2: Run repository quality checks**

Run: `pytest -q && ruff check . && mypy app config`

Expected: exit code `0` for each command.

- [ ] **Step 3: Run frontend checks**

Run: `npm run test && npm run build:web`

Expected: Vitest, TypeScript and Vite production build pass.

- [ ] **Step 4: Perform visual smoke validation**

Start the local API and Vite app using the project’s isolated runtime data.  Open Template Studio, create a draft, add one field, show failed preflight, add the missing marker declarations, publish, and open the generated PNG/PDF.  Record only the outcome and local URL in `PROGRESS.md`; do not commit runtime databases, evidence or logs.

- [ ] **Step 5: Document and commit**

Document that Phase A does **not** yet read uploaded photographs, decode QR, correct perspective, ingest ZIP packages, auto-fill OCR fields, create real queues, or produce mapped XLSX exports.  Also document the legacy `.xls` reader dependency: LibreOffice conversion works in the current environment only with an isolated user profile; future import must not rely on Excel COM.

```bash
git add PROGRESS.md docs/CODEX_HANDOFF.md
git commit -m "docs: record template phase a progress"
git push origin modular-architecture
```

## Plan self-review

- Coverage: Tasks 1–5 implement template identity/lifecycle, field geometry, safety preflight, print artifacts, storage-safe API and audit; Task 6 removes the current dead “模板与字段” navigation; Task 7 maps all nine supplied payroll/price files to four template families; Task 8 records explicit exclusions and verifies the result.
- Deliberate deferrals: controlled file upload, QR decoding/ArUco correction, immutable recognition attempts, queues/drafts/return/void/atomic next, and XLSX export mapping are Phases B–D.  They are not silently represented as completed in this phase.
- Consistency: lifecycle names use the approved `AUTO_PREFILLED` only in later recognition work; Phase A publication uses `DRAFT`, `READY_TO_PUBLISH` and `PUBLISHED`.  All QR checksum functions use the same deterministic `CRC32-low-16` algorithm.
