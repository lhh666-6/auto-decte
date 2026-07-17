# 工业表单前端重建实施计划

> **交给后续开发者：** 必须使用 `superpowers:test-driven-development`，严格按本文任务顺序逐项实施；每完成一个任务就运行该任务的验证命令并提交，不要先完成全部代码再补测试。

**目标：** 在不改变后端 API、审核状态机、权限矩阵、模板版本语义、导出批次规则、数据库结构和识别算法的前提下，把现有开发者式后台重建为以“图片证据与电子表格逐项核对”为核心的工业表单工作台。

**架构：** 保留现有 React Web、API Client 与 Shell Ports 分层。先把 `App.tsx` 中的审核逻辑无行为变化地拆出，再建立统一工作台骨架、图片与字段联动、业务语言字典和任务进度展示；随后加入浏览器路由与应用外壳，最后压缩模板、基础数据和导出模块。后端返回的技术状态和追溯数据保持原样，只在显示层转换为业务语言。

**技术栈：** React 18、TypeScript、Vite 5、Vitest、Testing Library、现有 `@form-detection/api-client`、现有 `@form-detection/shell-ports`，新增 `react-router-dom`。

---

## 产品规格来源与开发重点

本计划的**唯一产品规格来源**是用户提供的 `frontend_rebuild_summary.md`。本文只是把该文档拆成可测试、可提交的工程步骤，不增加新的产品功能，不改变原文优先级。组件名、测试文件名和提交粒度属于落地方法，不是额外产品需求。

如果执行中发现本计划与 `frontend_rebuild_summary.md` 的明确表述冲突，以该原始文档为准；先停止冲突任务，在 `docs/NEXT_TASK.md` 记录原文位置、冲突内容和影响，等待人工确认，不自行选择新方向。

接下来开发重点严格分为三阶段：

1. **第一阶段：核心审核闭环。** 统一双栏审核工作台、上传后原地处理、图片框与字段行双向联动、图片工具、三类任务共用骨架、固定底部动作栏、专属空状态。对应任务 1—9。
2. **第二阶段：统一应用外壳。** 浏览器路由、固定全局导航、统一按钮/状态/字号/颜色/间距、业务化状态文案、模块切换保留上下文。对应任务 10—11。
3. **第三阶段：压缩次级模块。** 模板创建抽屉与精简卡片、基础数据标签和业务表单、导出四步流程、技术信息进入追溯详情。对应任务 12—15。

原文到实施任务的追溯关系：

| `frontend_rebuild_summary.md` 内容 | 本计划任务 |
|---|---|
| 第 1—2 节：重建目标、信息架构与路由 | 1、10、11 |
| 第 3—7 节：双栏工作台、字段联动、三类任务、工具栏、空状态 | 3—9 |
| 第 8 节：模板中心 | 12 |
| 第 9 节：基础数据 | 13 |
| 第 10 节：导出数据 | 14 |
| 第 11—12 节：业务文案与状态码 | 1、8、11、15 |
| 第 13—15 节：错误、确认框、视觉规范 | 8、11、15 |
| 第 16—18 节：清理清单、实施优先级、验收标准 | 6—16 |
| 第 19 节：最终产品闭环 | 7、8、14、16 |
| 第 20 节：纯前端重建边界 | 0、9、16 |

除上述追溯范围外，不得新增登录、权限放宽、模板业务模型、纸张设计器、识别算法、数据库字段或后端接口改造。

---

## 0. 使用规则与范围

### 0.1 只读这些说明文件

开始前只读取：

1. `docs/CURRENT_STATUS.md`
2. `docs/NEXT_TASK.md`
3. `docs/DECISIONS.md`
4. `docs/FRONTEND_INTERACTION_GUIDE.md`
5. 本实施计划
6. 每个任务“允许读取”中列出的代码和测试

不要扫描整个仓库，不要读取 `node_modules`、`dist`、构建产物、历史 handoff、上传文件、模型文件或数据库内容。遇到计划未覆盖的问题，先在 `docs/NEXT_TASK.md` 的“执行中发现”记录，不要自行扩大范围。

### 0.2 固定业务边界

- 不修改任何 Python 后端代码、API 路由、数据库迁移、权限矩阵或识别算法。
- 不新增登录界面，不绕过现有权限；无权限时使用业务化提示。
- 二维码失败后绝不自动猜模板，必须选择精确已发布版本并填写原因。
- 已发布模板不可原地编辑；调优必须克隆新草稿。
- 正常首次确认继续使用 `confirm-and-claim-next`；已确认记录的更正继续使用 `confirm`。
- 离开含未保存修改的页面必须提醒。
- 导出筛选变化后，旧预览必须失效；重导必须关联真实旧批次并保留旧文件。
- 颜色只能辅助表达，所有状态同时显示文字。
- 技术 ID、哈希、内部状态码默认放入“追溯详情”或“高级信息”，不得删除。

### 0.3 已确认的接口能力与唯一阻塞项

现有接口能够完成：上传图片、重复图片处理、人工分类、识别任务状态查询、审核租约、暂存、确认、退回、作废、模板管理、基础数据管理、导出预览与批次下载。

识别任务进度使用现有 `GET /api/v1/tasks/{task_id}`，返回 `status`、`progress`、`step` 和 `error`。本计划不新增后端进度接口。

唯一不能由纯前端真实完成的是：**在 `RECAPTURE_REQUIRED` 原表单上上传一张新照片，并在数据库中永久保存“旧表单—新照片—新识别结果”的替换关系。** 现有 `POST /api/v1/imports` 会按新图片创建新表单，没有“替换当前表单证据”的生产接口。任务 9 只重建重拍页面和诚实提示，不得用 `localStorage` 或内存映射伪造永久追溯。该能力必须等独立后端任务获批。

### 0.4 每个提交的通用检查

在 `D:\半自动表单检测系统\.worktrees\modular-architecture\frontend` 执行：

```powershell
npm run typecheck
npm run test -w @form-detection/web
```

预期：TypeScript 无错误，Vitest 全部通过。若只是运行单个测试文件，任务末尾仍至少运行一次相关模块的全部测试。

---

## 1. 基线与业务语言字典

**允许读取：**

- `frontend/apps/web/src/review-model.ts`
- `frontend/apps/web/src/review-model.test.ts`
- `frontend/apps/web/src/TemplateLibrary_ds.tsx`
- `frontend/apps/web/src/MasterDataCenter_ds.tsx`
- `frontend/apps/web/src/ExportCenter_ds.tsx`

**新增：**

- `frontend/apps/web/src/ui/business-language.ts`
- `frontend/apps/web/src/ui/business-language.test.ts`

### 步骤

- [x] 先写失败测试，覆盖以下完整映射：
  - 审核状态：`IMPORTED`、`NEEDS_CLASSIFICATION`、`CLASSIFIED`、`RECOGNIZED`、`NEEDS_REVIEW`、`RECAPTURE_REQUIRED`、`CONFIRMED`、`CORRECTED`、`VOIDED`。
  - 导出状态：`NOT_EXPORTED`、`EXPORTED`、`REEXPORT_REQUIRED`。
  - 模板状态：`DRAFT`、`PREFLIGHT_FAILED`、`READY_TO_PUBLISH`、`PUBLISHED`、`DEPRECATED`、`RETIRED`。
  - 每个条目含 `label`、`description`、`nextAction`、`technicalLabel`。
  - 未知状态显示“未知状态”，并在 `technicalLabel` 保留原值。
- [x] 运行失败测试：

```powershell
npm run test -w @form-detection/web -- src/ui/business-language.test.ts
```

预期：因模块不存在而失败。

- [x] 实现只读字典和 `getReviewStatusCopy`、`getExportStatusCopy`、`getTemplateStatusCopy`。
- [x] 增加按钮文案常量，至少包含：上传表单照片、查找表单、开始审核、暂停审核、暂存修改、确认并审核下一张、保存本次修改、退回重新拍照、标记为无效、检查可导出的数据、生成 Excel。
- [x] 再运行同一测试，预期通过。
- [x] 暂不替换所有页面文案；本任务只建立单一来源。
- [x] 提交：

```powershell
git add frontend/apps/web/src/ui/business-language.ts frontend/apps/web/src/ui/business-language.test.ts
git commit -m "feat(frontend): add business language dictionary"
```

**验收：** 后续组件不得自行创建第二套状态映射；默认界面不直接显示英文状态码。

---

## 2. 补齐前端任务查询客户端

**允许读取：**

- `frontend/packages/api-client/src/review-workbench.ts`
- `frontend/packages/api-client/src/exports_ds.ts`
- `frontend/packages/api-client/src/index_ds.ts`
- `frontend/apps/web/src/review-api.test.ts`

**新增或修改：**

- 新增 `frontend/packages/api-client/src/tasks_ds.ts`
- 修改 `frontend/packages/api-client/src/index_ds.ts`
- 新增 `frontend/apps/web/src/task-api.test.ts`

### 步骤

- [x] 先写 `task-api.test.ts`，用 mock fetch 验证 `TaskApi.getTask("TASK-1")` 请求 `/api/v1/tasks/TASK-1`，并解析：

```ts
interface TaskStatusDetail {
  task_id: string;
  operation: string;
  resource_id: string;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED" | "INTERRUPTED" | string;
  progress: number;
  step: string | null;
  error: string | null;
}
```

- [x] 增加失败响应测试：非 2xx 必须抛出 `ApiRequestError`，不能只显示 `Failed to fetch`。
- [x] 运行测试，确认因客户端不存在而失败。
- [x] 实现 `TaskApi`，沿用现有 API Client 的请求错误解析方式。
- [x] 从 `index_ds.ts` 导出 `TaskApi` 和 `TaskStatusDetail`。
- [x] 运行：

```powershell
npm run build:api-client
npm run test -w @form-detection/web -- src/task-api.test.ts
```

预期：构建和测试通过。

- [x] 提交：

```powershell
git add frontend/packages/api-client/src/tasks_ds.ts frontend/packages/api-client/src/index_ds.ts frontend/apps/web/src/task-api.test.ts
git commit -m "feat(frontend): add task status client"
```

---

## 3. 无行为变化地拆分审核工作台

**允许读取：**

- `frontend/apps/web/src/App.tsx`
- `frontend/apps/web/src/review-correction.test.tsx`
- `frontend/apps/web/src/review-api.test.ts`
- `frontend/apps/web/src/review-model.ts`
- `frontend/apps/web/src/styles.css`

**新增或修改：**

- 新增 `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`
- 新增 `frontend/apps/web/src/workbench/workbench-types.ts`
- 修改 `frontend/apps/web/src/App.tsx`
- 修改 `frontend/apps/web/src/review-correction.test.tsx`

### 步骤

- [x] 先在现有回归测试增加以下断言：
  - 首次确认仍调用 `/confirm-and-claim-next`。
  - 已有正式记录的更正仍调用 `/confirm`，且不调用 `/confirm-and-claim-next`。
  - 无租约时写操作不可执行。
  - 有未保存修改时切换模块会出现确认提示。
- [x] 运行测试并确认新增断言在当前代码上通过，形成拆分保护网。
- [x] 把 `App.tsx` 中所有审核工作台状态、加载、上传、分类、租约、暂存、确认、退回、作废和渲染移动到 `ReviewWorkbenchPage.tsx`。
- [x] `workbench-types.ts` 只放页面级类型：`MobilePane`、`QueueKey`、`ReviewAction`、`DuplicateImportInfo`。API 类型继续从 API Client 导入。
- [x] `App.tsx` 暂时只保留四个功能区切换以及对 `ReviewWorkbenchPage`、模板、基础数据和导出组件的装配；本任务不改视觉、不加路由。
- [x] 运行：

```powershell
npm run test -w @form-detection/web -- src/review-correction.test.tsx
npm run typecheck
```

预期：行为完全不变，测试和类型检查通过。

- [x] 提交：

```powershell
git add frontend/apps/web/src/App.tsx frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx frontend/apps/web/src/workbench/workbench-types.ts frontend/apps/web/src/review-correction.test.tsx
git commit -m "refactor(frontend): extract review workbench page"
```

---

## 4. 字段问题排序与双向联动状态

**允许读取：**

- `frontend/apps/web/src/review-model.ts`
- `frontend/apps/web/src/review-model.test.ts`
- `frontend/packages/api-client/src/review-workbench.ts`

**新增：**

- `frontend/apps/web/src/workbench/field-navigation.ts`
- `frontend/apps/web/src/workbench/field-navigation.test.ts`

### 步骤

- [x] 先写纯函数测试，定义优先级：填写错误 > 必填缺失 > 低可靠度 > 需要人工确认 > 正常字段。
- [x] 测试 `selectFirstIssueFieldId(fields, edits, ruleFailures)`：加载表单后返回最高优先级问题字段；没有问题时返回第一个字段；空数组返回 `null`。
- [x] 测试 `nextFieldId` 和 `previousFieldId` 在首尾边界不越界。
- [x] 测试悬停字段与正式选中字段分离：清除 hover 不得改变 selected。
- [x] 运行测试，确认失败；随后实现函数并通过。
- [x] 所有判断复用 `reviewValueIssue`，不得创建不同的字段合法性规则。
- [x] 提交：

```powershell
git add frontend/apps/web/src/workbench/field-navigation.ts frontend/apps/web/src/workbench/field-navigation.test.ts
git commit -m "feat(frontend): add review field navigation"
```

---

## 5. 图片证据查看器与变换工具

**允许读取：**

- `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`
- `frontend/apps/web/src/review-model.ts`
- `frontend/packages/api-client/src/review-workbench.ts`
- `frontend/apps/web/src/styles.css`

**新增：**

- `frontend/apps/web/src/workbench/evidence-transform.ts`
- `frontend/apps/web/src/workbench/evidence-transform.test.ts`
- `frontend/apps/web/src/workbench/EvidenceToolbar.tsx`
- `frontend/apps/web/src/workbench/EvidenceViewer.tsx`
- `frontend/apps/web/src/workbench/EvidenceViewer.test.tsx`

### 步骤

- [x] 先测试纯变换：缩放限制为 25%–400%，旋转每次 90°，复位返回 100%/0°/零位移，拖动只改变位移。
- [x] 先写组件失败测试，覆盖：
  - 原图/校正图只在对应证据存在时可切换。
  - `+`、`-`、旋转、复位、显示/隐藏字段框可操作。
  - 鼠标滚轮缩放。
  - 点击字段框调用 `onSelectField(fieldId)`。
  - 选中框加粗，其他框降低透明度；hover 只浅色高亮。
  - 无校正图时显示原图且不渲染基于模板坐标的字段框。
- [x] 实现 `EvidenceToolbar` 和 `EvidenceViewer`。证据选择必须继续使用现有 `selectReviewEvidence` 语义。
- [x] 字段框坐标使用现有 `source_region`，按实际图片显示尺寸换算；不得修改后端坐标。
- [x] 增加选中字段裁片区域：优先显示 `FIELD_CROP` 且 `related_field_id` 匹配的证据；没有裁片时显示“该字段没有可用裁片”。
- [x] 运行：

```powershell
npm run test -w @form-detection/web -- src/workbench/evidence-transform.test.ts src/workbench/EvidenceViewer.test.tsx
```

预期：全部通过。

- [x] 提交：

```powershell
git add frontend/apps/web/src/workbench/evidence-transform.ts frontend/apps/web/src/workbench/evidence-transform.test.ts frontend/apps/web/src/workbench/EvidenceToolbar.tsx frontend/apps/web/src/workbench/EvidenceViewer.tsx frontend/apps/web/src/workbench/EvidenceViewer.test.tsx
git commit -m "feat(frontend): add evidence review tools"
```

---

## 6. 统一双栏工作台骨架

**允许读取：**

- `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`
- `frontend/apps/web/src/workbench/EvidenceViewer.tsx`
- `frontend/apps/web/src/review-correction.test.tsx`
- `frontend/apps/web/src/styles.css`

**新增或修改：**

- 新增 `frontend/apps/web/src/workbench/WorkbenchHeader.tsx`
- 新增 `frontend/apps/web/src/workbench/WorkbenchQueue.tsx`
- 新增 `frontend/apps/web/src/workbench/FieldReviewTable.tsx`
- 新增 `frontend/apps/web/src/workbench/FieldDetailPanel.tsx`
- 新增 `frontend/apps/web/src/workbench/WorkbenchActionBar.tsx`
- 新增 `frontend/apps/web/src/workbench/ReviewWorkbenchPage.test.tsx`
- 修改 `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`
- 修改 `frontend/apps/web/src/styles.css`

### 步骤

- [x] 先写布局与行为测试：
  - 桌面为左图右表，CSS 初始比例 46%/54%。
  - 点击图片字段框会滚动并聚焦对应“最终填写值”。
  - 点击字段行会选中并通知图片查看器定位。
  - hover 不改变正式选中项。
  - 加载后自动选择第一个问题字段。
  - 字段行同时显示“系统识别值、识别可靠度、最终填写值、文字状态”。
  - 底部操作栏为 sticky/fixed，并显示剩余问题数和租约到期时间。
- [x] 实现固定骨架：顶部表单上下文、左侧队列、中心双栏、下方详情、固定底部动作。
- [x] 桌面分隔线可拖动，宽度限制为图片 35%–65%，把用户选择保存到 `localStorage` 键 `review-workbench-split-percent`。
- [x] 窄屏使用“图片/电子表格”标签；切换时保留 `selectedFieldId` 和各自滚动位置。
- [x] 字段详情显示裁片、候选值、填报规则、主数据选项和错误说明。
- [x] 将状态文案全部改为任务 1 的业务字典；英文值仅放在追溯详情。
- [x] 运行：

```powershell
npm run test -w @form-detection/web -- src/workbench/ReviewWorkbenchPage.test.tsx src/review-correction.test.tsx
npm run typecheck
```

- [x] 提交：

```powershell
git add frontend/apps/web/src/workbench frontend/apps/web/src/styles.css frontend/apps/web/src/review-correction.test.tsx
git commit -m "feat(frontend): build unified review workbench"
```

---

## 7. 分类后原地显示识别进度

**允许读取：**

- `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`
- `frontend/packages/api-client/src/review-workbench.ts`
- `frontend/packages/api-client/src/tasks_ds.ts`
- `frontend/apps/web/src/review-api.test.ts`

**新增或修改：**

- 新增 `frontend/apps/web/src/workbench/ClassificationStage.tsx`
- 新增 `frontend/apps/web/src/workbench/RecognitionProgress.tsx`
- 新增 `frontend/apps/web/src/workbench/ClassificationStage.test.tsx`
- 修改 `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`

### 步骤

- [x] 先写失败测试：二维码失败时显示原因、精确已发布版本选择、分类原因和模板摘要；未选版本或未填原因不能提交。
- [x] 测试 `assignTemplate` 成功返回 `recognition_task_id` 后，不更换页面；每 500ms 查询一次任务状态。
- [x] 状态为 `RUNNING` 时显示百分比与业务化步骤：校正图片、裁切字段、生成识别结果。
- [x] 状态为 `SUCCEEDED` 时停止轮询，重新加载当前 workbench，并在同一双栏骨架中显示字段表。
- [x] 状态为 `FAILED`、`CANCELLED` 或 `INTERRUPTED` 时停止轮询，说明发生了什么和下一步如何重试。
- [x] 组件卸载或切换表单时使用 `AbortController` 或取消标记停止旧轮询；旧响应不得覆盖新表单。
- [x] 实现并运行：

```powershell
npm run test -w @form-detection/web -- src/workbench/ClassificationStage.test.tsx src/review-api.test.ts
```

- [x] 提交：

```powershell
git add frontend/apps/web/src/workbench/ClassificationStage.tsx frontend/apps/web/src/workbench/RecognitionProgress.tsx frontend/apps/web/src/workbench/ClassificationStage.test.tsx frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx
git commit -m "feat(frontend): keep classification progress in workbench"
```

---

## 8. 审核动作、快捷键、错误与空状态

**允许读取：**

- `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`
- `frontend/apps/web/src/workbench/WorkbenchActionBar.tsx`
- `frontend/apps/web/src/review-correction.test.tsx`
- `frontend/apps/web/src/styles.css`

**新增或修改：**

- 新增 `frontend/apps/web/src/workbench/useWorkbenchShortcuts.ts`
- 新增 `frontend/apps/web/src/workbench/useWorkbenchShortcuts.test.tsx`
- 新增 `frontend/apps/web/src/workbench/WorkbenchEmptyState.tsx`
- 修改工作台组件和样式

### 步骤

- [x] 先测试快捷键：
  - `Enter` 接受当前首选候选并选择下一个问题字段；在 textarea、select 打开或输入法组合期间不触发。
  - `Tab`/`Shift+Tab` 在字段间移动，同时保留浏览器可访问焦点行为。
  - `Ctrl+S` 仅在有租约且有未保存修改时暂存，并阻止浏览器保存网页。
  - `+`/`-`、`0`、`R` 只在图片查看器上下文生效。
- [x] 测试按钮按状态隐藏：不适用动作不长期置灰；无表单时只显示上传和查找；待分类显示分类动作；待审核显示暂存/确认；已确认后修改显示保存本次修改；待重拍显示重拍说明。
- [x] 实现三种专属空状态：待确认类型为空、待审核为空、待重新拍照为空。空状态不得渲染巨大空白双栏。
- [x] 把通用网络错误转换为三段式提示：发生什么、为何不能继续、下一步怎么做。保留 `ApiRequestError.code` 到追溯详情。
- [x] 退回和作废使用明确确认框并要求原因；保留现有 API 调用和审计语义。
- [x] 运行工作台全部测试并提交：

```powershell
npm run test -w @form-detection/web -- src/workbench src/review-correction.test.tsx
git add frontend/apps/web/src/workbench frontend/apps/web/src/styles.css
git commit -m "feat(frontend): complete review actions and empty states"
```

---

## 9. 待重新拍照页面的真实能力边界

**允许读取：**

- `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`
- `frontend/packages/api-client/src/review-workbench.ts`
- `docs/NEXT_TASK.md`

**新增或修改：**

- 新增 `frontend/apps/web/src/workbench/RecaptureStage.tsx`
- 新增 `frontend/apps/web/src/workbench/RecaptureStage.test.tsx`
- 修改 `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`

### 步骤

- [x] 先写测试：页面继续使用双栏骨架，显示上次照片、上次结果、退回原因、异常字段和历史记录入口。
- [x] 页面把“规则异常”统一显示为“待重新拍照”。
- [x] 主动作显示“上传新的表单照片”，但旁边必须明确说明：当前版本会创建一张新表单，尚不能自动关联为原表单的替换证据。
- [x] 上传按钮可复用现有导入流程；成功后打开新表单。不得显示“已替换原照片”或“追溯关系已保存”。
- [x] 在 `docs/NEXT_TASK.md` 的阻塞项保留独立后端需求：为原表单提交 replacement evidence、运行重新识别、保存 old/new evidence linkage 和审计事件。
- [x] 运行测试并提交：

```powershell
npm run test -w @form-detection/web -- src/workbench/RecaptureStage.test.tsx
git add frontend/apps/web/src/workbench docs/NEXT_TASK.md
git commit -m "feat(frontend): clarify recapture workflow boundary"
```

**验收：** 页面可用且不误导；“新旧照片永久追溯”在后端接口完成前仍是明确未完成项。

---

## 10. 浏览器路由与统一应用外壳

**允许读取：**

- `frontend/apps/web/package.json`
- `frontend/package-lock.json`
- `frontend/apps/web/src/main.tsx`
- `frontend/apps/web/src/App.tsx`
- `frontend/apps/web/src/TemplateStudio_ds.tsx`
- `frontend/apps/web/src/MasterDataCenter_ds.tsx`
- `frontend/apps/web/src/ExportCenter_ds.tsx`

**新增或修改：**

- 新增 `frontend/apps/web/src/app/router.tsx`
- 新增 `frontend/apps/web/src/app/AppShell.tsx`
- 新增 `frontend/apps/web/src/app/AppShell.test.tsx`
- 修改 `frontend/apps/web/src/main.tsx`
- 修改 `frontend/apps/web/src/App.tsx`
- 修改 `frontend/apps/web/package.json`
- 修改 `frontend/package-lock.json`

### 步骤

- [x] 在 `frontend` 目录安装路由：

```powershell
npm install react-router-dom@^6.28.0 -w @form-detection/web
```

- [x] 先用 `MemoryRouter` 写失败测试：一级导航为审核工作台、模板中心、基础数据、导出数据；当前项有 `aria-current="page"`；浏览器后退能回到上一位置。
- [x] 建立以下路由，不能改名：

```text
/workbench/type-confirmation
/workbench/review
/workbench/recapture
/workbench/:formId
/templates
/templates/:templateId/versions/:version
/templates/:templateId/draft
/master-data/employees
/master-data/work-orders
/master-data/products
/master-data/processes
/exports
```

- [x] `/` 重定向到 `/workbench/review`；未知地址显示应用内 404 和“返回审核工作台”。
- [x] `AppShell` 固定显示产品名、一级导航、服务状态、当前身份位置和用户菜单占位；不得新增登录功能。
- [x] 路由切换前复用现有未保存修改提醒；刷新后保留当前模块和表单 URL。
- [x] 旧的 `Feature` 全屏替换状态删除；队列选择改由 URL 驱动。
- [x] 运行：

```powershell
npm run test -w @form-detection/web -- src/app/AppShell.test.tsx src/review-correction.test.tsx src/export-center.test.tsx
npm run typecheck
```

- [x] 提交：

```powershell
git add frontend/apps/web/package.json frontend/package-lock.json frontend/apps/web/src/main.tsx frontend/apps/web/src/App.tsx frontend/apps/web/src/app
git commit -m "feat(frontend): add routed application shell"
```

---

## 11. 统一视觉令牌与响应式规则

**允许读取：**

- `frontend/apps/web/src/styles.css`
- `frontend/apps/web/src/app/AppShell.tsx`
- 本计划第 6、8、10 节涉及的组件

**新增或修改：**

- 新增 `frontend/apps/web/src/ui/StatusBadge.tsx`
- 新增 `frontend/apps/web/src/ui/StatusBadge.test.tsx`
- 修改 `frontend/apps/web/src/styles.css`

### 步骤

- [x] 先测试 `StatusBadge` 同时渲染文字和状态语义，不仅设置颜色。
- [x] 在 `:root` 定义设计令牌：主操作蓝、成功绿、警告橙、危险红、次要灰；基础字号 14px，辅助文字不低于 12px；间距 8/16/24/32px；圆角 8/10px。
- [x] 所有新增/保存/预览/下一步使用蓝色；绿色只用于成功或已启用状态；危险动作红色。
- [x] 审核工作台尽量全宽；模板、基础数据、导出内容最大宽度 1520px。
- [x] 减少卡片嵌套，优先使用标题栏、分隔线、浅色区、表格、抽屉和更多菜单。
- [x] 在 1280px 以上显示双栏，在窄屏显示图片/电子表格标签，在 768px 以下保持主要动作可见且不横向溢出。
- [x] 运行组件测试、类型检查和生产构建：

```powershell
npm run test -w @form-detection/web -- src/ui/StatusBadge.test.tsx src/workbench
npm run build:web
```

- [x] 提交：

```powershell
git add frontend/apps/web/src/ui frontend/apps/web/src/styles.css
git commit -m "style(frontend): unify industrial interface tokens"
```

---

## 12. 模板中心压缩与路由化

**允许读取：**

- `frontend/apps/web/src/TemplateLibrary_ds.tsx`
- `frontend/apps/web/src/TemplatePreview_ds.tsx`
- `frontend/apps/web/src/TemplateStudio_ds.tsx`
- `frontend/apps/web/src/TemplateCanvasEditor_ds.tsx`
- `frontend/apps/web/src/FieldInspector_ds.tsx`
- `frontend/apps/web/src/template-studio-state.test.ts`
- `frontend/apps/web/src/template-studio-model.test.ts`
- `frontend/apps/web/src/template-api.test.ts`

**新增或修改：**

- 修改上述模板组件
- 新增 `frontend/apps/web/src/TemplateLibrary_ds.test.tsx`
- 新增 `frontend/apps/web/src/TemplatePreview_ds.test.tsx`

### 步骤

- [x] 先测试模板库顶部工具栏含搜索、状态筛选、导入模板包、创建模板；“创建模板”打开抽屉或弹窗，不常驻左栏。
- [x] 模板卡片中文名优先，编号放次级位置；只保留一个上下文主操作；退役、放弃草稿等危险动作放入“更多”。
- [x] “模板包导入”继续禁用并显示“暂未开放”，不得假装已接通 API。
- [x] 通过路由打开精确只读版本或草稿；发布版本只读，调优操作克隆新草稿。
- [x] 预览页增加缩放、适合页面、适合宽度、复位、字段搜索、字段列表/画布双向联动、PDF/PNG 产物入口。
- [x] 技术文件名、字段编号和哈希移入高级信息。
- [x] 保持现有异步防串页测试：旧请求不得覆盖新选择。
- [x] 运行：

```powershell
npm run test -w @form-detection/web -- src/TemplateLibrary_ds.test.tsx src/TemplatePreview_ds.test.tsx src/template-studio-state.test.ts src/template-studio-model.test.ts src/template-api.test.ts
```

- [x] 提交：

```powershell
git add frontend/apps/web/src/TemplateLibrary_ds.tsx frontend/apps/web/src/TemplateLibrary_ds.test.tsx frontend/apps/web/src/TemplatePreview_ds.tsx frontend/apps/web/src/TemplatePreview_ds.test.tsx frontend/apps/web/src/TemplateStudio_ds.tsx frontend/apps/web/src/TemplateCanvasEditor_ds.tsx frontend/apps/web/src/FieldInspector_ds.tsx
git commit -m "feat(frontend): streamline template center"
```

---

## 13. 基础数据业务化表单

**允许读取：**

- `frontend/apps/web/src/MasterDataCenter_ds.tsx`
- `frontend/apps/web/src/master-data-api.test.ts`
- `frontend/packages/api-client/src/master-data_ds.ts`

**新增或修改：**

- 修改 `frontend/apps/web/src/MasterDataCenter_ds.tsx`
- 新增 `frontend/apps/web/src/MasterDataCenter_ds.test.tsx`
- 新增 `frontend/apps/web/src/master-data-form.ts`
- 新增 `frontend/apps/web/src/master-data-form.test.ts`

### 步骤

- [x] 先测试四个紧凑标签及正确路由：员工、工单、产品、工序；从产品 URL 打开时不得回到员工。
- [x] 左侧列表桌面宽度固定约 340px，右侧为当前记录详情；新增按钮放在当前目录标题旁。
- [x] 区分“目录为空”和“搜索无结果”的空状态。
- [x] 用业务表单替代直接 JSON 编辑：
  - 员工：员工编号、姓名、班组、岗位、联系电话、备注。
  - 工单：工单编号、关联产品、计划数量、开始日期、结束日期、负责人。
  - 产品：产品编码、产品名称、规格型号、计量单位。
  - 工序：工序编码、工序名称、标准顺序、工作站。
- [x] `master-data-form.ts` 负责业务字段与现有 attributes 对象双向转换；额外未知键进入“更多信息”键值编辑器，不得丢失。
- [x] 保持稳定编码不可修改、If-Match 乐观版本、停用/恢复、审计和冲突提示语义。
- [x] 冲突提示改为“该记录已被其他人修改，请刷新后重试”，技术版本放追溯详情。
- [x] 运行：

```powershell
npm run test -w @form-detection/web -- src/MasterDataCenter_ds.test.tsx src/master-data-form.test.ts src/master-data-api.test.ts
```

- [x] 提交：

```powershell
git add frontend/apps/web/src/MasterDataCenter_ds.tsx frontend/apps/web/src/MasterDataCenter_ds.test.tsx frontend/apps/web/src/master-data-form.ts frontend/apps/web/src/master-data-form.test.ts
git commit -m "feat(frontend): rebuild master data forms"
```

---

## 14. 导出数据四步流程

**允许读取：**

- `frontend/apps/web/src/ExportCenter_ds.tsx`
- `frontend/apps/web/src/export-center.test.tsx`
- `frontend/apps/web/src/export-api.test.ts`
- `frontend/packages/api-client/src/exports_ds.ts`

**修改：**

- `frontend/apps/web/src/ExportCenter_ds.tsx`
- `frontend/apps/web/src/export-center.test.tsx`

### 步骤

- [x] 先把现有测试扩展为四步可见流程：选择数据 → 检查数据 → 生成 Excel → 下载文件。
- [x] 筛选区使用业务名称；主按钮为“检查可导出的数据”。
- [x] 检查结果分为：将要导出的记录、无法导出的记录及原因、Excel 列对应关系。
- [x] 只有有效预览存在时显示“生成 Excel”；筛选变化立即使预览和创建资格失效。
- [x] 任务进行中显示业务进度；成功后在当前页面出现下载动作和历史记录。
- [x] 默认隐藏完整批次 ID、SHA-256、映射哈希、内部文件名和技术状态码；在“追溯详情”抽屉中完整保留并提供复制。
- [x] 重导文案说明：记录在上次导出后发生修改；选择包含旧数据的导出记录；系统生成修正版；旧文件继续保留。
- [x] 保留现有所有并发保护：旧预览响应、旧刷新响应、卸载后的请求都不得覆盖新状态。
- [x] 运行完整导出测试：

```powershell
npm run test -w @form-detection/web -- src/export-center.test.tsx src/export-api.test.ts
```

- [x] 提交：

```powershell
git add frontend/apps/web/src/ExportCenter_ds.tsx frontend/apps/web/src/export-center.test.tsx
git commit -m "feat(frontend): present export as four step flow"
```

---

## 15. 统一反馈、确认框与可访问性

**允许读取：**

- 本计划新增的所有 `src/ui` 组件
- 工作台、模板、基础数据、导出四个页面入口组件

**新增或修改：**

- 新增 `frontend/apps/web/src/ui/ProblemNotice.tsx`
- 新增 `frontend/apps/web/src/ui/ConfirmDialog.tsx`
- 新增 `frontend/apps/web/src/ui/TraceDetails.tsx`
- 新增 `frontend/apps/web/src/ui/ui-feedback.test.tsx`
- 修改四个页面入口组件

### 步骤

- [x] 先测试 `ProblemNotice` 必须有标题、原因和下一步动作；原始 code 只在追溯详情显示。
- [x] 先测试 `ConfirmDialog` 有可聚焦标题、说明、取消和明确危险动作；Esc 取消；关闭后焦点返回触发按钮。
- [x] 统一退回、作废、模板停用、放弃草稿、基础数据停用的确认框，不再使用原生 `prompt`。
- [x] 所有按钮使用“动作 + 对象”；图标按钮必须有 `aria-label`；导航、标签、表格、弹窗使用正确语义。
- [x] 键盘完成审核主路径：进入字段、修改值、暂存、确认、关闭弹窗，焦点顺序可预测。
- [x] 运行：

```powershell
npm run test -w @form-detection/web -- src/ui/ui-feedback.test.tsx src/workbench src/TemplateLibrary_ds.test.tsx src/MasterDataCenter_ds.test.tsx src/export-center.test.tsx
```

- [x] 提交：

```powershell
git add frontend/apps/web/src/ui frontend/apps/web/src/workbench frontend/apps/web/src/TemplateLibrary_ds.tsx frontend/apps/web/src/MasterDataCenter_ds.tsx frontend/apps/web/src/ExportCenter_ds.tsx
git commit -m "feat(frontend): unify feedback and confirmations"
```

---

## 16. 全量验收、文档收尾与推送

**允许读取或修改：**

- `docs/CURRENT_STATUS.md`
- `docs/NEXT_TASK.md`
- `docs/FRONTEND_INTERACTION_GUIDE.md`
- 本计划

### 自动验证

- [x] 在仓库根目录运行后端回归，确认纯前端重建没有破坏契约：

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app
```

预期基线：Python 至少 `264 passed`，Ruff 通过，mypy 通过；如果测试数增加，只要求无失败且记录新总数。

- [x] 在 `frontend` 目录运行：

```powershell
npm run test
npm run build:web
```

预期：全部前端测试、类型检查和生产构建通过。

**2026-07-17 执行记录：** Python `264 passed`，Ruff 通过，mypy `126 source files` 无问题；前端 `25` 个测试文件、`124 passed`，类型检查与 Web 生产构建通过。仓库 `.env` 是管理员试用配置，Python 全量测试显式覆盖为代码默认 `local-operator/OPERATOR`；系统临时目录权限受限时使用仓库内 `.pytest-final`，验证结束后已清理。

### 人工验收

- [x] 启动 API 和 Web，使用真实浏览器逐项检查：
  1. 上传照片后留在工作台并立即显示图片。
  2. 二维码失败时精确选择模板版本并填写原因。
  3. 分类后原地显示任务进度并转成字段表。
  4. 图片框与字段行点击/hover 双向联动。
  5. 缩放、滚轮、拖动、旋转、复位、原图/校正图、字段裁片工作正常。
  6. 默认定位首个问题字段；快捷键可用。
  7. 暂存、首次确认并下一张、更正、退回、作废保持原语义。
  8. 刷新和浏览器前进/后退保留正确路由。
  9. 模板、基础数据、导出都在统一外壳内。
  10. 窄屏切换图片/电子表格时选择和滚动位置不丢失。
  11. 默认无英文状态码、哈希和长技术 ID；追溯详情仍可查看。
  12. 待重拍页面明确说明当前 replacement API 限制，不宣称已保存新旧关联。

真实浏览器使用现有 API 数据完成非破坏性验收，并在 `390 × 844` 视口验证窄屏切换。涉及审核、分类、停用和导出写入的分支由组件/API 自动化测试覆盖，浏览器未修改共享演示数据。验收发现的英文导出排除原因已在 `e04b617` 修复并复验。

### 文档与提交

- [x] 更新 `CURRENT_STATUS.md`：实际测试数、当前 HEAD、已完成阶段、仍阻塞的 replacement evidence API。
- [x] 更新 `NEXT_TASK.md`：勾选已完成项，只保留真实未完成项；不要删除后端阻塞说明。
- [x] 更新 `FRONTEND_INTERACTION_GUIDE.md` 为重建后的真实交互，不再保留已经失效的旧按钮说明。
- [x] 检查文档没有占位词：

```powershell
rg -n "T[O]DO|T[B]D|待[补]|以后再[说]|similar t[o]|implement late[r]" docs/superpowers/plans/2026-07-17-frontend-rebuild-implementation.md docs/CURRENT_STATUS.md docs/NEXT_TASK.md docs/FRONTEND_INTERACTION_GUIDE.md
git diff --check
```

预期：第一条无输出，第二条无错误。

- [ ] 提交已完成；仍需在网络证书问题解除后确认远端没有新提交：

```powershell
git add docs/CURRENT_STATUS.md docs/NEXT_TASK.md docs/FRONTEND_INTERACTION_GUIDE.md docs/superpowers/plans/2026-07-17-frontend-rebuild-implementation.md
git commit -m "docs: close frontend rebuild implementation"
git fetch origin
git rev-list --left-right --count origin/modular-architecture...HEAD
```

预期：左侧为 `0`；如果左侧不为 `0`，先停止并与队友协调，不要强推。

- [ ] 推送（当前被本机 Git HTTPS 证书代理阻塞）：

```powershell
git push origin modular-architecture
git status --short --branch
```

预期：本地与 `origin/modular-architecture` 一致，工作树干净。

---

## 完成定义

只有同时满足以下条件，才能宣布前端重建完成：

- 16 个任务按顺序完成并有对应提交。
- 全量 Python、Ruff、mypy、前端测试、类型检查和生产构建全部通过。
- 核心审核工作台、统一路由外壳、模板中心、基础数据和导出四步流程通过人工验收。
- 现有业务不变量没有改变，旧证据、旧版本、旧模板和旧导出文件仍可追溯。
- `RECAPTURE_REQUIRED` 的 replacement evidence 后端能力如果仍不存在，必须继续明确标记为阻塞，不能以临时前端状态冒充完成。
- 工作树干净，提交已推送到 `origin/modular-architecture`，队友可以直接拉取继续协作。
