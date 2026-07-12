# Backup and Recovery Guide

## Backup

Backups are created using SQLite Online Backup API for consistent snapshots without
downtime. The backup service copies the database, evidence files, and export files
to a timestamped directory with a SHA-256 manifest.

### Creating a Backup

Backups are created programmatically through the application's API:
```
POST /api/v1/admin/backup
```

### Manual Backup

```bash
# Copy database
cp data/database/demo.db data/database/demo.db.backup

# Copy evidence and exports
cp -r data/evidence data/evidence.backup
cp -r data/exports data/exports.backup
```

## Restore

### Verification Before Restore

```bash
uv run python -m app.tools.verify_integrity_ds
```

### Restore Steps

1. **Stop the application**
2. **Backup current data** to a safe location
3. **Restore database** from backup
4. **Restore evidence files** from backup
5. **Restore export files** from backup
6. **Verify integrity** after restore
7. **Start the application**

### Integrity Check

```bash
# Standard check
uv run python -m app.tools.verify_integrity_ds

# JSON output for automation
uv run python -m app.tools.verify_integrity_ds --json
```

## Backup Contents

Each backup contains:
- `demo.db` - SQLite database snapshot
- `evidence/` - All imported evidence files
- `exports/` - All generated XLSX export files
- `manifest.json` - Backup metadata with SHA-256 hashes
