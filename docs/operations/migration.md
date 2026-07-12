# Database Migration Guide

## Prerequisites

- Python 3.11+ with uv
- PYTHONPATH set to project root (or run from project root)

## First-time Setup

```bash
# Run migrations
uv run alembic upgrade head

# Verify
uv run python -m app.tools.verify_integrity_ds
```

## Creating New Migrations

```bash
uv run alembic revision --autogenerate -m "description"
```

Always review the generated migration before applying.

## Migrating an Existing Database

```bash
# Backup first
# (use the backup service via application or manual SQLite copy)

# Apply pending migrations
uv run alembic upgrade head
```

## Rollback

```bash
# Roll back one step
uv run alembic downgrade -1

# Roll back to baseline
uv run alembic downgrade 001
```

## Important

- SQLite has limited ALTER TABLE support. Additive changes (new tables, new columns) work best.
- Always backup before upgrading a production database.
- Migration state is stored in the `alembic_version` table.
