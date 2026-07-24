# Mobile Inspector Inspection Workflow Closeout

> 日期: 2026-07-24
> 分支: modular-architecture
> 基线: fe149ec

## 1. Executive Result
**INSPECTOR_READY_WITH_NOTES** -- Core P0 resolved. Inspector can now complete full inspection workflow.

## 2. Root Cause Analysis

### Root Cause 1: Inspection Window Timing Gap
- **File**: `app/adapters/database/bamboo_process_repository_ds.py:499`
- **Before**: Inspection window created ONLY at SUPERVISOR submission
- **After**: Window created at production completion (SORT for SORTING, DRYING for DIPPING_DRYING)
- **Impact**: Inspector saw records as AVAILABLE but no window existed -> could not claim/fill/submit

### Root Cause 2: moisture_points Missing from API
- **File**: `frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx:115-133`
- **Before**: submitInspection sent conclusion/targetStage but NO moisture_points
- **After**: 3-20 point numeric inputs + moisturePoints parameter in API call
- **Impact**: Core inspection data (detection point values) completely missing from frontend and backend

## 3. Fixes

### Backend

| File | Lines | Change |
|------|-------|--------|
| `app/adapters/database/bamboo_process_repository_ds.py` | 499-524 | Inspection window created at last production stage (SORT for SORTING, DRYING for DIPPING_DRYING), not only at SUPERVISOR |
| `app/api/routers/mobile_bamboo_ds.py` | 626-666 | Added `moisture_points_json` form parameter, parsed as JSON array of decimals, validated 3-20 range |
| `app/api/routers/mobile_bamboo_ds.py` | 669-674 | Pass `moisture_points` through to `bamboo_operations.create_inspection` |
| `app/application/bamboo_operations_ds.py` | -- | `create_inspection` accepts and stores `moisture_points` parameter |
| `app/modules/bamboo_process/facade_ds.py` | -- | Inspection facade updated to pass moisture_points |
| `app/api/schemas/bamboo_process_ds.py` | -- | Inspection schema extended with moisture_points field |

### Frontend

| File | Lines | Change |
|------|-------|--------|
| `frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx` | 115-168 | `moisturePoints` state with 3-20 numeric inputs, included in `submitBambooInspection` payload, reset to `[0,0,0]` after success |
| `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx` | 338-345 | Test updated for radio-group UI: clicks "合格", "核对并提交检测记录", "确认提交", asserts moisturePoints in payload |
| `frontend/apps/web/src/mobile/v3/BambooV3HomePage.tsx` | -- | V3 home page inspection queue integration |
| `frontend/apps/web/src/mobile/v3/BambooV3SubmissionsPage.tsx` | -- | Submissions page inspection history |
| `frontend/packages/api-client/src/mobile_ds.ts` | -- | API client `submitBambooInspection` signature updated with moisturePoints |

## 4. Inspector Task Model

INSPECTOR now uses Inspection Window based model instead of production stage model:

- **Inspection Window** opens automatically when the last production stage completes (SORT for SORTING forms, DRYING for DIPPING_DRYING forms), with a 2-hour deadline
- **Claim flow**: Inspector claims an open window (idempotent), enters their queue
- **Submit flow**: Inspector fills moisture points (3-20), selects conclusion (合格/不合格 via radio), optionally captures photos/audio for nonconforming results
- **Confirmation**: Two-step -- "核对并提交检测记录" opens confirmation dialog, "确认提交" finalizes
- **Server authority**: Moisture average computed server-side from submitted points
- **History**: Inspector sees past inspections from real Inspection records
- **Draft isolation**: Pending submissions isolated by employee, factory, and device

## 5. Inspection Form

### moisture_points UI
- 3 to 20 numeric input fields for detection point values
- Server validates: must be JSON number array, max 20 entries
- Average computed and displayed server-side

### Conclusion
- Radio group: 合格 (CONFORMING) / 不合格 (NONCONFORMING)
- NONCONFORMING unlocks: target stage selector, text evidence, photo capture, audio recording

### Evidence
- Photo capture button ("点击拍照") for nonconforming submissions
- Audio recording button ("点击录音") for nonconforming submissions
- Text notes for nonconforming submissions

### Confirmation
- "核对并提交检测记录" opens review dialog
- "确认提交" executes submission with idempotency key
- "返回修改" dismisses dialog

## 6. Key Flows Verified
- Claim idempotency ✅
- Inspection submit idempotency ✅
- Draft owner isolation ✅
- History from real Inspection records ✅
- Average server-authoritative ✅

## 7. Role Boundaries
- Inspector cannot submit production stages ✅
- Supervisor cannot submit inspections ✅
- PLANT_MANAGER Mobile 403 preserved ✅

## 8. Remaining Items
- Real-Stack E2E not yet implemented
- Screenshots not captured
- 1 Vitest regression (fixed in same round -- BambooV3Pages.test.tsx:330)

## 9. Final Classification
**INSPECTOR_READY_WITH_NOTES**
