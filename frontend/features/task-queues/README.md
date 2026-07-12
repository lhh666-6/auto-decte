# task-queues

**Status:** Contract skeleton — TypeScript interfaces only.

Task queue management UI. Displays queued, running, completed, and failed
extraction jobs. Allows operators to prioritise, cancel, or re-run tasks.

## Scope

- Queue dashboard (pending / running / completed / failed counts)
- Per-job detail view (status, progress %, started-at, error log)
- Priority controls (move up/down, set priority level)
- Cancel / re-run individual or batch jobs
- Real-time status updates (WebSocket or polling)

## Dependencies

- `@form-detection/api-client` — job CRUD, status polling
- `@form-detection/shell-ports` — notifications on job completion
- React
