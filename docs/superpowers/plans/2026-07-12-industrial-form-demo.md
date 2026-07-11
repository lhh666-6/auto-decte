# Industrial Form Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-local industrial production form Demo that works end-to-end without OCR or AI, then adds replaceable recognition and optional AI capabilities while preserving evidence, versions, audit history, and XLSX traceability.

**Architecture:** Streamlit calls application services backed by domain entities and repository interfaces. SQLite, local evidence storage, image recognition, optional AI/vector search, and XLSX export are adapters; automated outputs are candidates and never overwrite confirmed facts.

**Tech Stack:** Python 3.11, Streamlit, SQLAlchemy, Alembic, Pydantic, OpenCV, openpyxl, pytest, Ruff, mypy.

---

## Collaboration protocol

- Developer A executes Tasks 1–6 and Task 9.
- Developer B executes Tasks 7–8 and Task 10 after being added as a repository collaborator.
- Both developers execute Task 11 together; the developer who did not author a PR reviews it.
- Use one branch per task group: `phase-0-bootstrap`, `phase-1-manual-loop`, `phase-2-query-export`, `phase-3-recognition`, `phase-4-rules-audit`, `phase-5-ai-vector`, `phase-6-acceptance`.
- Before starting a branch: `git switch main`, `git pull --ff-only`, then `git switch -c <branch>`.
- Every PR must include code, tests, and the matching `PROGRESS.md` update.

## Planned file map

```text
app/
  domain/models.py              # immutable business entities and enums
  domain/rules.py               # deterministic validation rules
  application/ports.py          # repository and adapter protocols
  application/import_forms.py   # evidence import orchestration
  application/review_forms.py   # confirmation and correction use cases
  application/query_forms.py    # exact SQLite-backed search
  application/export_forms.py   # export orchestration and trace links
  adapters/database/models.py    # SQLAlchemy persistence models
  adapters/database/repositories.py
  adapters/storage/local.py      # content-addressed evidence storage
  adapters/recognition/opencv.py # quality, QR, crop, OCR/OMR candidates
  adapters/ai/disabled.py        # no-op safe default
  adapters/ai/provider.py        # opt-in structured suggestions
  adapters/vector/local.py       # optional local similarity index
  services/container.py          # dependency construction
  ui/main.py                     # Streamlit navigation
  ui/pages/*.py                  # focused workflow pages
config/settings.py               # environment-driven configuration
config/fields/default.json       # standard field dictionary
tests/unit/                       # domain and adapter unit tests
tests/integration/                # database, storage, export, workflow tests
tests/fixtures/                   # synthetic non-sensitive fixtures
PROGRESS.md                       # plain-text handoff state
```

### Task 1: P0 repository and quality bootstrap — Developer A

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `app/__init__.py`
- Create: `app/ui/main.py`
- Create: `config/settings.py`
- Create: `tests/unit/test_settings.py`
- Create: `PROGRESS.md`

- [ ] **Step 1: Write a failing settings test**

```python
from pathlib import Path
from config.settings import Settings


def test_settings_keep_runtime_data_below_configured_root(tmp_path: Path) -> None:
    settings = Settings(data_root=tmp_path, ai_enabled=False)
    assert settings.database_path == tmp_path / "database" / "demo.db"
    assert settings.evidence_root == tmp_path / "evidence"
    assert settings.ai_enabled is False
```

- [ ] **Step 2: Run the test and confirm the missing module failure**

Run: `python -m pytest tests/unit/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config.settings'`.

- [ ] **Step 3: Add project configuration and minimal settings**

Declare Python `>=3.11,<3.12` and dependencies for Streamlit, SQLAlchemy, Alembic, Pydantic Settings, OpenCV headless, openpyxl, pytest, Ruff, and mypy. Implement `Settings` with `data_root`, `ai_enabled=False`, derived `database_path`, and derived `evidence_root`. Add a Streamlit page that displays “工业级产量数据采集 Demo”. Ignore `.env`, `data/`, generated XLSX, caches, virtual environments, and secrets; keep `.env.example` tracked.

- [ ] **Step 4: Add the initial handoff record**

Create `PROGRESS.md` with headings for P0–P6. Under P0 record owner, branch, start date, completed items, remaining items, verification command/result, latest commit, known issues, and next action. Use explicit values; use `尚未提交` only until the commit in Step 6.

- [ ] **Step 5: Verify bootstrap**

Run: `python -m pytest -v && python -m ruff check .`
Expected: all tests pass and Ruff reports no errors.

- [ ] **Step 6: Commit and push**

```powershell
git add pyproject.toml .gitignore .env.example README.md app config tests PROGRESS.md
git commit -m "chore: bootstrap local demo application"
git push -u origin phase-0-bootstrap
```

Update the P0 latest-commit field with the resulting hash in a follow-up documentation commit before opening the PR.

### Task 2: P1 domain model and SQLite persistence — Developer A

**Files:**
- Create: `app/domain/models.py`
- Create: `app/application/ports.py`
- Create: `app/adapters/database/models.py`
- Create: `app/adapters/database/repositories.py`
- Create: `tests/unit/test_domain_models.py`
- Create: `tests/integration/test_form_repository.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Write failing domain tests**

Test that a new `Form` starts with `review_status=IMPORTED`, `export_status=NOT_EXPORTED`, and version zero; test that `RecognitionAttempt`, `EvidenceFile`, and `RecordVersion` cannot replace one another and retain distinct IDs.

- [ ] **Step 2: Run the tests**

Run: `python -m pytest tests/unit/test_domain_models.py -v`
Expected: FAIL because domain types do not exist.

- [ ] **Step 3: Implement domain types and repository protocols**

Implement string enums for all review, export, record, AI, evidence, and value-source states specified in the design. Implement dataclasses for Form, FormField, RecognitionAttempt, EvidenceFile, RecordVersion, AuditEvent, and ExportBatch. Define protocols for form, evidence, version, audit, and export repositories without importing SQLAlchemy.

- [ ] **Step 4: Write and run a failing persistence test**

The integration test creates a temporary SQLite database, saves one form with two record versions, reloads it, and asserts that both versions remain while only version 2 is current.

Run: `python -m pytest tests/integration/test_form_repository.py -v`
Expected: FAIL because SQLAlchemy persistence is absent.

- [ ] **Step 5: Implement persistence and verify**

Create normalized SQLAlchemy tables with foreign keys and uniqueness constraints for business IDs. Repository correction operations must insert a new record version and update the form pointer in one transaction.

Run: `python -m pytest tests/unit/test_domain_models.py tests/integration/test_form_repository.py -v`
Expected: PASS.

- [ ] **Step 6: Update progress and commit**

Commit: `feat: add versioned form persistence`.

### Task 3: P1 immutable evidence import — Developer A

**Files:**
- Create: `app/adapters/storage/local.py`
- Create: `app/application/import_forms.py`
- Create: `tests/integration/test_evidence_import.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Write failing import tests**

Cover SHA-256 calculation, same-file duplicate detection, same-form duplicate detection, content-addressed destination paths, original-file preservation, and audio rejection when no trigger condition is present.

- [ ] **Step 2: Confirm failure**

Run: `python -m pytest tests/integration/test_evidence_import.py -v`
Expected: FAIL because storage and import services do not exist.

- [ ] **Step 3: Implement local storage and import orchestration**

Store files below `data/evidence/<type>/<sha256-prefix>/<file-id>.<ext>`. Open destinations with exclusive creation, never overwrite an existing path, and return file ID plus relative URI. `ImportForms` must create `EvidenceFile`, `Form`, and `AuditEvent(IMPORT)` records transactionally after the file is safely stored.

- [ ] **Step 4: Verify failure safety**

Add a test that forces the database write to fail and asserts the original source remains untouched and no false successful import is returned.

Run: `python -m pytest tests/integration/test_evidence_import.py -v`
Expected: PASS.

- [ ] **Step 5: Update progress and commit**

Commit: `feat: import immutable form evidence`.

### Task 4: P1 manual review and version confirmation — Developer A

**Files:**
- Create: `app/application/review_forms.py`
- Create: `app/ui/pages/review.py`
- Create: `tests/unit/test_review_service.py`
- Create: `tests/integration/test_manual_loop.py`
- Modify: `app/ui/main.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Write failing review tests**

Test that confirmation creates version 1, correction creates version 2 and supersedes version 1, every action adds an AuditEvent with before/after/reason/actor/evidence IDs, and an OCR candidate is not a confirmed value.

- [ ] **Step 2: Confirm failure**

Run: `python -m pytest tests/unit/test_review_service.py -v`
Expected: FAIL because `ReviewForms` is missing.

- [ ] **Step 3: Implement review service and page**

The service accepts `form_id`, complete field values, actor, reason, and evidence IDs. It validates optimistic version equality, inserts a new immutable RecordVersion, updates current pointers, writes AuditEvent, and changes review state. The page shows original evidence, candidates, rules, history, and editable confirmed values on one screen.

- [ ] **Step 4: Verify the no-OCR end-to-end path**

The integration test imports a synthetic image, assigns a template manually, enters values, confirms the form, reloads it, and asserts the current values and complete audit chain.

Run: `python -m pytest tests/integration/test_manual_loop.py -v`
Expected: PASS with AI and recognition adapters disabled.

- [ ] **Step 5: Update progress and commit**

Commit: `feat: complete manual review loop`.

### Task 5: P2 exact query and trace view — Developer A

**Files:**
- Create: `app/application/query_forms.py`
- Create: `app/ui/pages/search.py`
- Create: `app/ui/pages/trace.py`
- Create: `tests/integration/test_query_and_trace.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Write failing query tests**

Create fixtures spanning form ID, employee, work order, date, template version, review/export states, audio, correction, export batch, exception code, and confidence. Assert combined filters use AND semantics and trace returns evidence, attempts, versions, audits, and exports.

- [ ] **Step 2: Confirm failure**

Run: `python -m pytest tests/integration/test_query_and_trace.py -v`
Expected: FAIL because query services are absent.

- [ ] **Step 3: Implement exact SQL query and trace pages**

Build parameterized SQLAlchemy queries only; do not use vector results for exact totals. Paginate results and show stable links from a result row to a trace page.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/integration/test_query_and_trace.py -v`
Expected: PASS.

- [ ] **Step 5: Update progress and commit**

Commit: `feat: add exact search and evidence trace`.

### Task 6: P2 XLSX export and reverse trace — Developer A

**Files:**
- Create: `app/application/export_forms.py`
- Create: `app/adapters/export/xlsx.py`
- Create: `app/ui/pages/export.py`
- Create: `tests/integration/test_xlsx_export.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Write failing export tests**

Assert only current confirmed/exportable versions appear; the workbook contains official data, exceptions/review, summary, and export-info sheets; each official row carries export batch, form, and version identifiers; file hash and included records are persisted; correcting an exported record sets `REEXPORT_REQUIRED`; a new export never overwrites an old workbook.

- [ ] **Step 2: Confirm failure**

Run: `python -m pytest tests/integration/test_xlsx_export.py -v`
Expected: FAIL because exporter is absent.

- [ ] **Step 3: Implement exporter and preview**

Use openpyxl and configurable mappings. Write to a unique filename containing export type, timestamp, and batch ID. Save ExportBatch only after the workbook is closed and SHA-256 is calculated. The preview must list excluded records and field-level errors.

- [ ] **Step 4: Verify traceability**

Reload the saved workbook, take one official-data row, call the trace service using its identifiers, and assert the original image and audit events are reachable.

Run: `python -m pytest tests/integration/test_xlsx_export.py -v`
Expected: PASS.

- [ ] **Step 5: Update progress and commit**

Commit: `feat: export traceable xlsx batches`.

### Task 7: P3 image pipeline and classification — Developer B

**Files:**
- Create: `app/application/recognize_forms.py`
- Create: `app/adapters/recognition/opencv.py`
- Create: `app/ui/pages/classification.py`
- Create: `tests/unit/test_image_pipeline.py`
- Create: `tests/integration/test_classification.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Write failing tests with synthetic fixtures**

Test rotation, perspective, blur, glare, missing-corner classification, QR-first template selection, low-confidence fallback to `NEEDS_CLASSIFICATION`, and manual reclassification creating an audit event plus a new recognition run.

- [ ] **Step 2: Confirm failure**

Run: `python -m pytest tests/unit/test_image_pipeline.py tests/integration/test_classification.py -v`
Expected: FAIL because recognition adapter is absent.

- [ ] **Step 3: Implement deterministic image stages**

Expose `assess_quality`, `correct_geometry`, `read_template_qr`, and `crop_fields`. Return typed results and reason codes; never update confirmed field values. Persist corrected images and crops as new EvidenceFile records.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/unit/test_image_pipeline.py tests/integration/test_classification.py -v`
Expected: PASS.

- [ ] **Step 5: Update progress and commit**

Commit: `feat: add image quality and classification pipeline`.

### Task 8: P3 digit OCR and OMR candidates — Developer B

**Files:**
- Create: `app/adapters/recognition/digits.py`
- Create: `app/adapters/recognition/omr.py`
- Create: `tests/unit/test_digit_and_omr.py`
- Create: `tests/integration/test_recognition_attempts.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Write failing candidate tests**

Test one-cell-one-digit output, ambiguous candidates, blank cells, checked/unchecked/ambiguous OMR, confidence bounds, model version persistence, crop evidence linkage, and append-only repeated attempts.

- [ ] **Step 2: Confirm failure**

Run: `python -m pytest tests/unit/test_digit_and_omr.py tests/integration/test_recognition_attempts.py -v`
Expected: FAIL because recognizers are absent.

- [ ] **Step 3: Implement recognizer adapters**

Each recognizer returns candidate value, confidence, engine, model version, and reason code. Recognition orchestration appends RecognitionAttempt and routes risky results to review; it never assigns `current_value`.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/unit/test_digit_and_omr.py tests/integration/test_recognition_attempts.py -v`
Expected: PASS.

- [ ] **Step 5: Update progress and commit**

Commit: `feat: add digit and omr recognition candidates`.

### Task 9: P4 deterministic rules and audit completeness — Developer A, reviewed by B

**Files:**
- Create: `app/domain/rules.py`
- Create: `app/ui/pages/exceptions.py`
- Create: `tests/unit/test_rules.py`
- Create: `tests/integration/test_audit_completeness.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Write a parameterized failing rule suite**

Cover required fields, ranges, `qualified + defective <= total`, valid employee/work order, duplicate form, current version, post-export correction, and complete export mapping. Assert every failure contains rule code, field ID, severity, and message.

- [ ] **Step 2: Confirm failure**

Run: `python -m pytest tests/unit/test_rules.py -v`
Expected: FAIL because rule engine is absent.

- [ ] **Step 3: Implement pure rules and exception queue**

Rules take an immutable context and return results without database or AI calls. Application services persist results and route failures to the exception queue.

- [ ] **Step 4: Audit all mutating use cases**

The integration test invokes import, reclassification, recognition, correction, confirmation, void, export, and recalculation, then asserts actor, timestamp, before/after, reason, and evidence IDs are present when applicable.

Run: `python -m pytest tests/unit/test_rules.py tests/integration/test_audit_completeness.py -v`
Expected: PASS.

- [ ] **Step 5: Update progress and commit**

Commit: `feat: enforce deterministic rules and audit trail`.

### Task 10: P5 optional AI and vector adapters — Developer B, reviewed by A

**Files:**
- Create: `app/adapters/ai/disabled.py`
- Create: `app/adapters/ai/provider.py`
- Create: `app/adapters/vector/local.py`
- Create: `tests/unit/test_ai_contract.py`
- Create: `tests/integration/test_ai_disabled.py`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Write contract tests**

Validate structured suggestions contain form ID, risk, summary, evidence-backed suggestions, missing information, and `requires_human_confirmation=True`. Reject unknown fields, silent mutations, and suggestions without evidence.

- [ ] **Step 2: Write disabled-mode integration test**

Run the import-to-export path with missing API credentials and `ai_enabled=False`; assert AI status is `NOT_RUN` or `UNAVAILABLE` and the workbook is still produced.

- [ ] **Step 3: Implement safe adapters**

Make the disabled adapter the default. The provider adapter receives redacted context, parses strict structured output, stores it separately, and never calls review mutation methods. Vector search returns ranked references only; exact filtering remains in SQLite.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/unit/test_ai_contract.py tests/integration/test_ai_disabled.py -v`
Expected: PASS without network or credentials.

- [ ] **Step 5: Update progress and commit**

Commit: `feat: add optional evidence-backed ai review`.

### Task 11: P6 full acceptance and handoff — Both developers

**Files:**
- Create: `tests/integration/test_acceptance_scenarios.py`
- Create: `docs/acceptance-report.md`
- Modify: `README.md`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Encode all mandatory scenarios**

Cover normal no-audio flow, E99 with audio, damaged QR with manual classification, ambiguous digits, blur/glare/missing corner/perspective, quantity closure failure, duplicate file/form, correction before and after export, AI unavailable, vector results without mutation, and XLSX-to-original-evidence tracing.

- [ ] **Step 2: Run the complete quality gate**

Run: `python -m pytest -v && python -m ruff check . && python -m mypy app config`
Expected: all tests pass; Ruff and mypy report no errors.

- [ ] **Step 3: Measure Demo performance and accuracy**

Run the approved 30–50-image technical dataset and record classification accuracy, image acceptance, digit accuracy, key-field row accuracy, false automatic release rate, duplicate interception, traceability, manual correction trace rate, processing time, and AI-disabled result in `docs/acceptance-report.md`.

- [ ] **Step 4: Complete handoff documentation**

README must contain Windows setup, configuration, database initialization, Streamlit start, tests, backup, data privacy, branch workflow, and recovery steps. Set completed P0–P6 sections in `PROGRESS.md` to explicit results and commit hashes.

- [ ] **Step 5: Commit and open final PR**

Commit: `test: verify end-to-end demo acceptance`.

## Per-PR completion checklist

- [ ] The assigned tests were written before implementation and their initial failure was observed.
- [ ] All affected tests pass locally.
- [ ] No original evidence or historical version can be overwritten.
- [ ] Every mutation produces the required AuditEvent.
- [ ] AI-disabled operation remains valid.
- [ ] UI displays actionable failure reasons.
- [ ] README/config examples reflect the change.
- [ ] `PROGRESS.md` lists commands, results, commit hash, known issues, and next action.
- [ ] No secrets, real employee data, recordings, generated database, or generated XLSX files are staged.
