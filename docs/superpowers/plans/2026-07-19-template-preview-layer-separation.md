# Template Preview Layer Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 模板预览默认显示真实黑白打印产物，并把蓝色字段识别框限制在用户主动开启的调试层中。

**Architecture:** 复用模板版本已有 `PRINT_PNG`/`PNG` 产物作为业务版面，不重新实现打印渲染。`TemplatePreview` 增加本地显示模式，默认只渲染打印图片；开启“显示识别区域”后，才在同一图片上叠加可选择字段框。打印 PDF/PNG 下载接口和模板版本不变。

**Tech Stack:** React 18、TypeScript、Testing Library、Vitest、现有 Template API。

---

### Task 1: 业务版面与识别调试层分离

**Files:**
- Modify: `frontend/apps/web/src/TemplatePreview_ds.tsx`
- Modify: `frontend/apps/web/src/TemplatePreview_ds.test.tsx`
- Modify: `frontend/apps/web/src/styles.css`

- [x] **Step 1: 写默认业务版面失败测试**

在 `TemplatePreview_ds.test.tsx` 增加断言：加载版本后默认显示 `alt="小时工资表业务版面"` 的打印 PNG；页面存在“业务版面”和“显示识别区域”切换；默认没有 `预览字段 工时` 按钮。

- [x] **Step 2: 写调试层失败测试**

点击“显示识别区域”后，断言 `预览字段 工时` 出现并可与字段列表双向选择；再次切回“业务版面”后识别框消失。

- [x] **Step 3: 写无 PNG 产物失败测试**

构造只有 PDF 的版本，断言业务版面显示“尚未生成 PNG 预览，请先完成发布前检查或重新生成打印产物”，但 PDF 下载仍可用。

- [x] **Step 4: 运行测试确认失败**

Run: `npm --prefix frontend run test -w @form-detection/web -- src/TemplatePreview_ds.test.tsx`

Expected: 新测试因缺少版面切换和打印图片而失败。

- [x] **Step 5: 实现最小显示模式**

在 `TemplatePreview_ds.tsx`：

```ts
type PreviewMode = "business" | "recognition";

function isPngArtifact(kind: string): boolean {
  return kind.toUpperCase().includes("PNG");
}
```

默认 `business`；从 `version.artifacts` 选择首个 PNG 类产物；以 `<img>` 填满纸张区域。只有 `recognition` 模式才渲染字段 overlay，字段列表和搜索继续保留。

- [x] **Step 6: 添加打印图片样式**

在 `styles.css` 增加 `.preview-business-image` 和显示模式按钮选中态。图片必须完整包含于纸张，不裁切、不改变宽高比；overlay 使用绝对定位并位于图片上方。

- [x] **Step 7: 运行局部验证**

Run:

```powershell
npm --prefix frontend run test -w @form-detection/web -- src/TemplatePreview_ds.test.tsx
npm --prefix frontend run typecheck
```

Expected: `TemplatePreview_ds.test.tsx` 全部通过，TypeScript 无错误。

- [x] **Step 8: 浏览器冒烟**

打开 `/templates`，进入任一已发布真实模板：默认只见黑白打印版；开启识别区域后出现蓝色字段框；PDF/PNG 下载不变。只检查这一页，不重复审核、导出或实体闭环。

- [ ] **Step 9: 提交**

```powershell
git add frontend/apps/web/src/TemplatePreview_ds.tsx frontend/apps/web/src/TemplatePreview_ds.test.tsx frontend/apps/web/src/styles.css docs/NEXT_TASK.md docs/CURRENT_STATUS.md docs/superpowers/plans/2026-07-19-template-preview-layer-separation.md
git commit -m "feat(templates): separate print and recognition preview layers"
```
