# Mobile Workflow Usability Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复竹丝移动端人员管理、笼号检索、检测窗口、审核动作、自动缓存、历史和 PWA 安装体验。

**Architecture:** 在现有独立表单模型上增加后端可选项/人员/按笼号查询契约；前端按角色呈现独立工作入口。草稿缓存保持纯客户端并按身份隔离，审核和权限判断仍以服务端为准。

**Tech Stack:** FastAPI、SQLAlchemy、React、TypeScript、Vite PWA、Vitest、Pytest。

---

### Task 1: 预设职位与厂长人员管理

**Files:**
- Modify: `app/application/bamboo_operations_ds.py`
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Modify: `app/api/schemas/bamboo_process_ds.py`
- Modify: `frontend/packages/api-client/src/mobile_ds.ts`
- Modify: `frontend/apps/web/src/mobile/v3/BambooV3ProfilePage.tsx`
- Test: `tests/api/test_mobile_bamboo_operations_ds.py`
- Test: `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx`

- [x] 增加当前角色可见的预设职位、本厂人员和新增人员接口。
- [x] 拒绝未知或停用职位，删除厂长操作时自动创建职位的行为。
- [x] 将换岗申请、换岗审批、本厂人员拆成独立 UI，并使用中文选择控件。
- [x] 新增人员时生成工号、设置初始 PIN、绑定本厂和预设职位。

### Task 2: 笼号检索与检测窗口

**Files:**
- Modify: `app/modules/bamboo_process/facade_ds.py`
- Modify: `app/modules/bamboo_process/state_machine_ds.py`
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Modify: `frontend/packages/api-client/src/mobile_ds.ts`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx`
- Test: `tests/modules/test_bamboo_process_facade_ds.py`
- Test: `tests/api/test_mobile_bamboo_operations_ds.py`
- Test: `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx`

- [x] `tasks` 支持笼号查询并在服务端按工厂/角色/步骤过滤。
- [x] 为检测人返回生产签字完成、主管尚未签字的候选记录。
- [x] 浸胶、干燥和检测工作页改为先搜索笼号再展示记录。
- [x] 保留异常阻止主管签字的规则。

### Task 3: 草稿缓存、本人历史与 PWA 安装

**Files:**
- Create: `frontend/apps/web/src/mobile/storage/bamboo-drafts.ts`
- Create: `frontend/apps/web/src/mobile/pwa/usePwaInstall.ts`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooStageForm.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx`
- Modify: `frontend/apps/web/src/mobile/v3/BambooV3SubmissionsPage.tsx`
- Modify: `frontend/apps/web/src/mobile/v3/BambooV3ProfilePage.tsx`
- Test: `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx`

- [x] 实现按账号/工厂/设备/记录/步骤隔离的本地草稿读写和清理。
- [x] 所有输入变更自动保存，挂载时恢复，成功提交后清理。
- [x] 提交记录读取竹丝本人步骤与检测历史。
- [x] 捕获 PWA 安装事件并提供安装状态与不支持时指引。

### Task 4: 主管通过与厂长即时审核

**Files:**
- Modify: `config/settings.py`
- Modify: `app/adapters/database/bamboo_process_repository_ds.py`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooRecordDetailPage.tsx`
- Test: `tests/integration/test_bamboo_process_repository_ds.py`
- Test: `frontend/apps/web/src/mobile/bamboo/bamboo.test.tsx`

- [x] 将厂长审核默认等待时间设为零并在零值时不执行时间门禁。
- [x] 将主管回退表单改为显式打开的独立面板。
- [x] 保持主管通过按钮直接提交 `SUPERVISOR` 签字。

### Task 5: 集中验证与运行服务

**Files:**
- Verify all files above.

- [x] 运行 Bamboo 后端模块、仓储和 API 测试。
- [x] 运行前端移动端聚焦测试、TypeScript 检查和生产构建。
- [x] 运行 Ruff 与 mypy。
- [x] 重启 8000 后端并通过 5173 局域网地址验证各角色登录和关键接口。
