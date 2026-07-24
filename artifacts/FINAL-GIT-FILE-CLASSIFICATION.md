# Final Git File Classification

> 日期: 2026-07-24
> 分支: modular-architecture
> 基线: fe149ec
> 来源: `git status --short --untracked-files=all`

## MUST_COMMIT (alembic migrations -- schema changes)

```
alembic/versions/034_correction_fields_export_record_count_ds.py
alembic/versions/035_plant_termination_reason_transfer_note_ds.py
alembic/versions/036_inspector_claim_idempotency_ds.py
```

## OPTIONAL_DOC (closeout reports, audit docs, plans)

### Closeout & Audit Reports (artifacts/*.md)
```
artifacts/FINAL-PILOT-UNIFIED-AUDIT.md
artifacts/FINAL-RELEASE-AUDIT.md
artifacts/FINANCE-ADMIN-FRONTEND-CLOSEOUT.md
artifacts/MOBILE-INSPECTOR-CLOSEOUT.md
artifacts/P0-1-plant-production-projection-fix-report.md
artifacts/P0-2-plant-payroll-projection-fix-report.md
artifacts/P0-2-precommit-audit-report.md
artifacts/P1-P2-outbox-owner-isolation-completion-report.md
artifacts/PILOT-COMMIT-CANDIDATE.txt
artifacts/PILOT-READY-FINAL-CLOSEOUT.md
artifacts/PLANT-WEB-TRUTHFULNESS-CLOSEOUT.md
artifacts/POST-PUSH-PILOT-HARDENING-REPORT.md
artifacts/mobile-pwa-p0-2-to-p0-6-completion-report.md
artifacts/p1p2-fix-report.md
artifacts/web-three-role-completion-report.md
artifacts/web-three-role-final-report.md
```

### Architecture Plans
```
docs/superpowers/plans/模块化工业程序增量架构设计_完善版.md
```

## TEST_EVIDENCE (test output, screenshots, validation data)

```
artifacts/mobile-layout-validation/
    acceptance-summary.md
    git-diff-check.txt
    git-diff-name-status.txt
    git-diff-numstat.txt
    git-diff-stat.txt
    git-status.txt
    summary.md
    tasklist-word-diff.txt
    vitest-baseline.txt
    vitest-current.txt

artifacts/mobile-v3-ui-optimization/
    修改报告.md

artifacts/acceptance/
    20260723-221732/
    20260723-224041/
    20260723-224427/
    20260723-232649/
    20260723-232823/
    20260724-002522/

frontend/artifacts/playwright/
    html-report/index.html
    test-output/.last-run.json
```

## RUNTIME (databases, temp files, logs -- NEVER commit)

```
.runtime/
    api-plant-web.stderr.log
    api-plant-web.stdout.log

.analysis/                          (LibreOffice profile data -- 3 profiles, ~400+ files)
    lo-profile-1/
    lo-profile-2/
    lo-profile-3/

.codex-pet-runs/                    (pixel art generation -- Lance pet sprites)
    lance/
```

## DO_NOT_COMMIT (spreadsheets, handoff, random files)

```
handoff.md

叉车工日工资计算表.xls
工业级产量数据采集_Demo开发文档_V2.0.docx
开片组日工资计算表.xls
碳化、油炉人员日工资计算表.xls
热压岗位日工资计算表.xls
竹丝装架日工资计算表.xls
装架组工资计算表.xls
计时工日工资计算表.xls
```

## Summary

| Classification | Count | Action |
|---------------|-------|--------|
| MUST_COMMIT | 3 | Add in next commit (alembic migrations) |
| OPTIONAL_DOC | 17 | Commit or leave untracked (documentation only) |
| TEST_EVIDENCE | 4 dirs | Leave untracked or add to .gitignore |
| RUNTIME | 3 dirs | Already in .gitignore (.runtime, .analysis, .codex-pet-runs) |
| DO_NOT_COMMIT | 9 | Never commit (spreadsheets, handoff, binary docs) |

**Note**: All files listed under OPTIONAL_DOC, TEST_EVIDENCE, RUNTIME, and DO_NOT_COMMIT should be added to `.gitignore` if they are not already covered.
