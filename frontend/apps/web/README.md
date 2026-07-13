# web

**Status:** 可运行的 React/Vite 审核工作台（Web Shell）。

Browser-based frontend application. Targets modern browsers (Chrome, Firefox,
Safari, Edge). Uses Web implementations of Shell Ports.

## Stack

- React 18+ with TypeScript
- React Router for client-side routing
- Vite as build tool
- Tailwind CSS for styling

## 当前已实现

- 深海蓝控制台、固定审核队列侧栏和“左图右表”审核布局；
- 通过 `@form-detection/api-client` 获取表单详情、历史、证据与审核租约；
- 原图字段框与右侧字段表双向选中，候选值可在底部抽屉采用；
- 人工确认值可编辑；确认动作使用版本前置条件和审核租约；
- Web 通知只通过 `@form-detection/shell-ports` 调用，未直接使用 Tauri API。

## 尚未实现

- 真实队列计数、规则结果、模板/主数据/导出页面和任务进度；
- 草稿保存、退回/作废原因、字段裁切详情及真正的“下一张”队列导航；
- Tauri v2 Rust 壳与桌面 Port 的真实实现。

## Shell Port implementation

All shell ports use the Web (browser) implementations from
`@form-detection/shell-ports/web_ds.ts`:

| Port           | Web Implementation |
|----------------|-------------------|
| FilePort       | `<input type="file">` + FileReader |
| CameraPort     | `MediaDevices.getUserMedia` |
| ScannerPort    | **Not available** — desktop only |
| AudioPort      | `MediaRecorder` API |
| NotificationPort | `Notification` API |

## Getting started

```bash
cd frontend
npm install
npm run dev -w apps/web
```
