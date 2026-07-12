# desktop

**Status:** Contract skeleton — placeholder.

Tauri-based desktop application. Packages the React frontend as a native
Windows binary with access to OS-level capabilities (file system, scanner,
system notifications).

## Stack

- Tauri v2 (Rust backend + webview frontend)
- React 18+ with TypeScript
- Vite as build tool

## Shell Port implementation

Shell ports use the Desktop (Tauri) implementations from
`@form-detection/shell-ports/desktop_ds.ts`. Each port delegates to a
Tauri Rust plugin or IPC command:

| Port           | Desktop Implementation |
|----------------|----------------------|
| FilePort       | `@tauri-apps/plugin-dialog` + `plugin-fs` |
| CameraPort     | Tauri IPC → Rust camera capture |
| ScannerPort    | Tauri IPC → Rust SANE bindings |
| AudioPort      | Tauri IPC → Rust audio capture |
| NotificationPort | `@tauri-apps/plugin-notification` |

## Getting started

```bash
cd frontend
npm install
cd apps/desktop
npm run tauri dev
```
