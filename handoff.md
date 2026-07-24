# Handoff — 2026-07-22 14:40

## Where we are

移动端 V3 主体已在独立 worktree `D:\半自动表单检测系统\.worktrees\bamboo-process-v3` 的分支 `codex/mobile-v3-replacement` 完成，当前 HEAD 为 `48b30fe`，工作树干净。根目录仍在 `modular-architecture`，有用户原有未提交文件，禁止 reset/checkout/覆盖。

已完成提交（新到旧）：

- `48b30fe feat(mobile): complete V3 work and account pages`
- `852e734 fix(demo): repair Bamboo Chinese identities`
- `30b09e9 fix(pwa): retire cached legacy mobile shell`
- `aa36d2d feat(mobile): add V3 login and role home`
- `f4310b8 docs(mobile): keep finance approval on web`
- `ef460f3 feat(mobile): replace legacy shell with V3 navigation`
- `50557c0 docs(mobile): plan V3 replacement`
- `dac4495 docs(mobile): specify V3 full replacement`

## Next action

先修下面 P0/P1，跑全量验证；全部绿后将 `codex/mobile-v3-replacement` 合并进根 worktree 的 `modular-architecture`，不得覆盖根目录现有脏文件。

## 未完成项

### P0：合并前必须完成

1. **实际演示数据库尚未执行中文修复。** 工具和测试已提交，但 `D:\半自动表单检测系统\data\database\demo.db` 中 ZS001/JZ001/GZ001/JC001/ZG001/CZ001/CW001 仍是 `???`。
   - 在 V3 worktree 中显式运行：
     `python -m app.tools.repair_bamboo_demo_ds --db "D:\半自动表单检测系统\data\database\demo.db"`
   - PIN 为 `2468`。随后逐个验证登录返回姓名、职位、工厂“竹丝示范一厂”，并确认 QA001 未变化。

2. **移动路由缺少角色边界。** 财务和无 `bamboo_role` 的账号可通过直输 `/mobile/work` 或 `/mobile/records/:id` 绕过首页。
   - 相关文件：`frontend/apps/web/src/app/router.tsx`、`frontend/apps/web/src/mobile/session/RequireMobileSession.tsx`、`frontend/apps/web/src/mobile/v3/MobileV3Shell.tsx`。
   - 财务访问任何受保护 `/mobile/*` 时仅显示“财务审批请前往网页端”及网页入口；未分配角色仅显示等待厂长/管理员分配；两者隐藏四栏生产导航。
   - 登录后竹丝账号固定进入 `/mobile/home`，不要让 `returnTo` 绕过角色落点。

3. **两个旧正式路由仍渲染旧组件。** `/mobile/record/sheet-piece` 和 `/mobile/record/team-sheet-piece` 必须删除或 `Navigate replace` 到 V3 页面，任何正式 `/mobile/*` 不得渲染旧框架。

4. **已有测试仍锁定旧登录文案。** `frontend/apps/web/src/mobile/mobile-routes.test.tsx:92,100` 仍断言“工业工资表系统/试点版本”，当前 13 项中 2 项失败。改为断言 V3“竹丝工序记录”和新版授权提示，然后跑全量前端测试。

5. **PWA 开发清理只识别 V3 缓存。** `frontend/apps/web/src/pwa/pwa-cache-names.ts` / `register-sw.ts` 应按稳定前缀删除本应用 V1/V2/V3 缓存，同时保留“不得删除其他应用缓存”的测试。

6. **安全区和主题 meta 未收尾。** `frontend/apps/web/index.html` 增加 `viewport-fit=cover`，theme-color 从旧 `#0F2742` 改为 `#17653a`；工作/详情颜色统一为 `#17653a`、`#26804d`、`#f3f5f4`。

### P1：业务完整性

7. **主管流程不完整。** 目前只有一个 conclusion/note 和选择性回退；还需前三工序（分选、浸胶、干燥）独立评价，并允许主管处理检测异常。涉及 `BambooStageForm.tsx`、`BambooOperationsPanel.tsx` 和正式 API payload/tests。

8. **详情分层/版本历史不足。** 当前所有可进详情的角色都能看到全部提交；需按角色和已开放层级裁剪。签字卡还未显示版本，失效历史也未折叠；必要时扩展 DTO/API。

9. **离线提交展示有缺口。** `BambooV3SubmissionsPage.tsx` 的 `Promise.all` 会在远端失败时连本地草稿/outbox 一起不显示；outbox `countAll()` 未按当前用户隔离；竹丝阶段表单还缺离线草稿保存/恢复（正式签字仍必须联网）。

10. **厂长人员配置/未来角色只是初步入口。** 后端仍使用固定 `BambooRole` 枚举。短期应移除“可直接输入未来职务”的误导文案；完整方案需动态角色定义、权限映射、员工查询、变更原因、二次确认和历史记录。

### P2：交互细节

11. 含水率输入仍是 `type=number`；交接要求 `type=text + inputmode=numeric`、过滤非数字、1–100 校验、无步进箭头。

12. 尚未做最后真实浏览器验收、API/Vite 重启、完整代码质量复审和合并。

## 已有验证结果

- V3/PWA 聚焦测试：31 passed。
- 中文修复工具：3 passed；相关后端 identity/auth/Bamboo 回归：11 passed；目标 Ruff 通过。
- 业务 V3/Bamboo：18 passed；TypeScript typecheck 通过。
- PWA：14 passed；生产 build 通过，产物含 `form-detection-web-v3` cacheId。
- 目前已知失败：`mobile-routes.test.tsx` 2 个旧文案断言。

## 建议验证命令

从 `D:\半自动表单检测系统\.worktrees\bamboo-process-v3\frontend` 运行：

```powershell
npm test
npm test -w @form-detection/api-client
npm run build:web
```

从 V3 worktree 根目录运行：

```powershell
ruff check app alembic tests config
mypy app config
pytest -q
```

然后重启 API/Vite，在 `http://localhost:5173/mobile/login` 用七个账号 + PIN `2468` 验收四栏、中文身份、角色拦截、财务网页端引导和 `/mobile/work`。

## 根 worktree 注意事项

根分支 `modular-architecture` 当前已有用户改动/未跟踪文件，包括 `docs/acceptance-report.md`、删除的旧计划、`.analysis/`、`.codex-pet-runs/`、多个 XLS/DOCX 等。它们与本任务无关，合并时全部保留。不要执行 `git reset --hard` 或 `git checkout --`。

## 需求来源

- 原型：`C:\Users\lenovo\OneDrive\xwechat_files\wxid_4raj20c8b79r22_250f\msg\file\2026-07\竹丝工序记录-原型V3(1).html`
- 工程交接：同目录 `竹丝工序记录-原型V3-工程交接.md`
- 正式规格：V3 worktree 内 `docs/superpowers/specs/2026-07-22-mobile-v3-full-replacement-design.md`
- 实施计划：V3 worktree 内 `docs/superpowers/plans/2026-07-22-mobile-v3-full-replacement.md`

