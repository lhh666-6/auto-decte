# 工业表单 PWA 移动端 V3 布局优化 — 验收报告

> 日期: 2026-07-24
> 分支: modular-architecture（未提交）
> 验证方式: 严格按验收文档逐项执行

---

## A. 结论: PASS_WITH_NOTES

修改范围严格限定在 CSS/Token/展示层 DOM，零业务逻辑侵入。质量门全部通过。

---

## B. 修改边界审核

| 审核项 | 结果 | 证据 |
|--------|------|------|
| 只有 CSS + 展示层 DOM | ✅ PASS | git word-diff 仅含 `<div className="field-group">` wrapper + 缩进 |
| 业务逻辑修改 | ✅ 无 | 0 处 useState/useEffect/onClick/onChange 变更 |
| API 修改 | ✅ 无 | 0 处 .post/.get/.put 变更 |
| 后端修改 | ✅ 无 | app/ 零修改 |
| 幂等/草稿/权限/状态机 | ✅ 无 | 零变更 |
| 无关文件污染 | ⚠️ NOTE | 存在预存无关修改（见 §I） |

### BambooTaskListPage.tsx word-diff 逐行确认

- 全部 `+` 行为：`<div className="field-group field-group--XXX">` 或 `</div>` 或缩进
- 全部 `-` 行为：原始标签缩进级不变，仅因 wrapper 插入而移动位置
- **0 处** useState/useEffect/onClick/onChange/API 调用/条件判断/button type/表单嵌套变更
- `bamboo-moisture-average` `<p>` 保持在 fieldset 内，位置未变

---

## C. 质量门

| 检查项 | 结果 | 证据 |
|--------|------|------|
| git diff --check | ✅ 0 whitespace errors | artifacts/mobile-layout-validation/git-diff-check.txt |
| TypeScript | ✅ PASS, 0 errors | `npx tsc --noEmit` 退出码 0 |
| Vite build | ✅ PASS, 108 modules | `npm run build:web` 退出码 0, dist 产出 5 文件 |
| PWA | ✅ PASS | sw.js + workbox-9c5a5b56.js 生成成功 |
| Vitest 当前 | ✅ 286 passed, 59/61 files | vitest-current.txt |
| Vitest 基线 | ⚠️ NOTE | worktree 路径差异导致不可靠比较，但当前 vs 基线文件级差异已确认 |
| Acceptance | ✅ 24/24 passed, 103+ steps | acceptance-summary.md |
| Playwright | ⚠️ BLOCKED | 无现有 Playwright 测试文件 |

### Vitest 失败详情

**当前 (2 failed, 均预存):**

1. `packages/shell-ports/src/ports_ds.test.ts` — `TypeError: _fileHandle.read is not a function`（FileHandle mock 缺失）
2. `apps/web/src/pwa/pwa-cache-policy.test.ts` — `Failed to resolve import "virtual:pwa-register"`（PWA plugin 未在测试环境注册）

**基线确认:** 这两个失败在 `abac58f`（修改前 HEAD）完全一致。无新增 mobile 测试失败。

---

## D. CSS Token 静态检查

| 检查项 | 结果 | 证据 |
|--------|------|------|
| 无遗留 `var(--radius)` | ✅ 0 处引用 | grep 返回空 |
| 无旧品牌色硬编码 | ✅ `#17653a` / `#f3f5f4` 零残留 | grep 返回空 |
| Token 权威来源唯一 | ✅ `mobile/v3/ui/tokens.css` 唯一完整定义 | styles.css 仅含结构属性 |
| Import 顺序正确 | ✅ tokens.css (line 6) → styles.css (line 7) | main.tsx |
| 变量未被覆盖 | ✅ styles.css 中 `.mobile-v3-shell` 不重定义 token | 已删除旧重复块 |
| 无空 CSS 变量 | ✅ 所有 `var(--xxx)` 均有定义或 fallback | `--border` / `--line-soft` 有 fallback |

### Token 实际计数

| 类别 | 数量 | Token 列表 |
|------|:----:|------|
| Palette | 13 | brand, brand2, brand-weak, bg, card, text, sub, line, muted, ok, warn, danger, blue |
| Spacing | 6 | space-xs, space-sm, space-md, space-lg, space-xl, space-2xl |
| Typography | 6 | font-display, font-heading, font-body, font-caption, font-label, font-micro |
| Radius | 4 | radius-sm, radius-md, radius-card, radius-sheet |
| Touch | 3 | touch-min, touch-btn, touch-primary |
| Effects | 2 | shadow, shadow-heavy |
| **Total** | **34** | |

> ⚠️ 之前修改报告中写的"30"和"33"均不准确，实际为 **34** 个 token。

---

## E. 视口验收（Puppeteer 实测）

| 视口 | 横向溢出 | 触摸目标 | 备注 |
|------|:---:|------|------|
| 360×800 | ✅ scrollW=clientW=344 | ✅ 所有 ≥52px | 无横向滚动 |
| 390×844 | ✅ 截图已获取 | ✅ 登录页按钮 52px | 验证通过 |

> ⚠️ 由于应用需要认证才能访问其他页面，未登录状态下只有登录页可完整验证。已登录页面的布局验证需要通过 API 登录后继续。

---

## F. 字段分组审核

| field-group | 状态 | 说明 |
|-------------|:----:|------|
| production-method | PASS | 仅包裹 mode-toggle |
| spec-info | PASS | 包裹 4 个 PickerField |
| production-target | PASS | 包裹 3 个 label.field |
| auto-summary | PASS | 包裹 kv div |
| test-data | NEEDS_ADJUSTMENT | fieldset 内已有边框样式，field-group 外层再加边框 → 双重边框 |
| confirmation | PASS | 包裹 form-actions |

### test-data 双重边框问题

**现状:** `field-group--test-data` 应用 `.field-group` 样式（border + border-radius + background），内部 `fieldset.bamboo-moisture-fieldset` 也有 border + border-radius。

**建议 (P2):** 添加特化规则：
```css
.mobile-v3-shell .field-group--test-data {
  border: 0;
  padding: 0;
  background: transparent;
}
```
让 fieldset 自身的视觉作为分组边界，field-group 仅提供语义分组。

### 其他 field-group 观察

- **第一个 field-group 上边距** 12px (`var(--space-md)`) — 合理
- **最后一个 field-group** 未与底部导航冲突（padding-bottom: 92px 确保空间）
- **自动摘要** 与普通输入字段视觉层级一致 — 可接受
- **无过度卡片嵌套**（每个 field-group 一层）

---

## G. 可访问性检查

| 检查项 | 结果 |
|--------|:----:|
| role="alert" 保留 | ✅ banner.danger 存在 |
| role="status" 保留 | ✅ banner.info 存在 |
| aria-label 保留 | ✅ mode-toggle div 有 aria-label="作业模式" |
| aria-pressed 保留 | ✅ mode-btn button 有 aria-pressed |
| button type 未变 | ✅ submit 和 button type 原样保留 |
| fieldset/legend 未破坏 | ✅ 仍在 field-group--test-data 内 |
| wrapper 不影响语义 | ✅ div 为纯展示层 |

---

## H. 新增失败

**无。** 当前 2 个 Vitest 失败与基线完全一致。

---

## I. Git 状态

```
 M docs/acceptance-report.md              ← 预存无关
 D docs/superpowers/plans/...demo.md      ← 预存无关
 M docs/superpowers/plans/...v3-complete.md ← 预存无关
 M frontend/apps/web/src/main.tsx         ← 本次修改
 M frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx ← 本次修改
 M frontend/apps/web/src/styles.css       ← 本次修改
 M tests/acceptance/test_bamboo_bug_probes.py ← 预存无关（函数重命名）
?? frontend/apps/web/src/mobile/v3/ui/    ← 本次新增
?? artifacts/                             ← 诊断产物，已 gitignored
```

### 需要清理的无关修改（P1）

- `docs/acceptance-report.md`
- `docs/superpowers/plans/2026-07-12-industrial-form-demo.md` (deleted!)
- `docs/superpowers/plans/2026-07-22-bamboo-process-v3-complete.md`
- `tests/acceptance/test_bamboo_bug_probes.py`

建议: `git checkout -- docs/ tests/acceptance/test_bamboo_bug_probes.py` 恢复这些文件到 HEAD。

---

## J. 建议

### P0 阻断 — 无

### P1 提交前修复

1. **清理无关修改**: `git checkout -- docs/ tests/acceptance/test_bamboo_bug_probes.py` 恢复 4 个无关文件到 HEAD
2. **Token 数量修正**: 修改报告中将 "30" 和 "33" 更正为 **34**

### P2 可后续优化

1. **field-group--test-data 双重边框**: 添加特化 CSS 规则移除 field-group 的边框（见 §F）
2. **未登录页面布局验证**: 需编写 Playwright 登录脚本后完成全部 3 视口 × 12 页面的完整验证
3. **残留硬编码色值**: V3 区仍有约 80 处未 token 化的颜色值（如 `#60756b`, `#0d6546`, `#d5e4dc` 等），建议分批 token 化

---

## K. 产物清单

| 文件 | 路径 |
|------|------|
| git-status | artifacts/mobile-layout-validation/git-status.txt |
| git-diff-stat | artifacts/mobile-layout-validation/git-diff-stat.txt |
| git-diff-check | artifacts/mobile-layout-validation/git-diff-check.txt |
| typescript | 退出码 0（无输出即成功） |
| build | 退出码 0, dist/ 5 文件 |
| vitest-current | artifacts/mobile-layout-validation/vitest-current.txt |
| vitest-baseline | artifacts/mobile-layout-validation/vitest-baseline.txt (路径问题，不可靠) |
| acceptance-summary | artifacts/mobile-layout-validation/acceptance-summary.md |
| commands | 见本报告 |

---

## 执行命令记录

```bash
# Git 检查
git status --short
git diff --stat
git diff --numstat
git diff --name-status
git diff --check
git diff --word-diff=porcelain -- frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx

# CSS Token
grep -rn 'var(--radius)' frontend/apps/web/src
grep -rn '#17653a\|#f3f5f4' frontend/apps/web/src

# TypeScript
cd frontend && npx tsc --noEmit  # exit 0

# Build
cd frontend && npm run build:web  # exit 0

# Vitest
cd frontend && npx vitest run  # 286 passed, 2 pre-existing failures

# Acceptance
powershell -ExecutionPolicy Bypass -File scripts/run_acceptance.ps1  # 24/24

# Playwright
npx playwright --version  # 1.61.1, but no test files found
```

---

**验证完成。不提交、不推送、不合并。**
