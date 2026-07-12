# web

**Status:** Contract skeleton — placeholder.

Browser-based frontend application. Targets modern browsers (Chrome, Firefox,
Safari, Edge). Uses Web implementations of Shell Ports.

## Stack

- React 18+ with TypeScript
- React Router for client-side routing
- Vite as build tool
- Tailwind CSS for styling

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
