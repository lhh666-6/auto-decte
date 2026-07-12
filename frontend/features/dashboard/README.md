# dashboard

**Status:** Contract skeleton — TypeScript interfaces only.

Main dashboard showing system-wide metrics, recent activity, and quick-action
widgets. Serves as the default landing page after login.

## Scope

- Volume metrics (forms processed today / week / month)
- Success / error rate charts
- Queue depth over time
- Operator performance summary
- Recent activity feed
- Quick-action cards (start review, upload batch, view queue)

## Dependencies

- `@form-detection/api-client` — metrics, activity feed
- React + charting library
