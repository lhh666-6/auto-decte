# exports-trace

**Status:** Contract skeleton — TypeScript interfaces only.

Export and audit trail UI. Handles data export (CSV, JSON, PDF) and provides
a searchable activity trace for compliance and debugging.

## Scope

- Export wizard (format, field selection, date range, filters)
- Scheduled export configuration
- Export history and download
- Audit trail viewer (who did what, when)
- Activity log search and filter
- Export manifest generation

## Dependencies

- `@form-detection/api-client` — export endpoints, audit log
- `@form-detection/shell-ports` — file save dialog (desktop only)
- React
