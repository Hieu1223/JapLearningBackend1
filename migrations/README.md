# Database Migration: old_db → current DB

This folder contains a repeatable migration from the old Supabase dump
(`ref/old_db.sql`) into the current application database. It is designed to be
re-run against production by pointing it at the real target database.

## What gets migrated

Tables in the old dump that have an equivalent model in the current codebase
(`app/database/.../schema.py`):

| Old table            | Current table            | Notes                                  |
|----------------------|--------------------------|----------------------------------------|
| `public.user`        | `user`                   | 1:1                                    |
| `public.authuser`    | `authuser`               | 1:1                                    |
| `public.usersettings`| `usersettings`           | 1:1                                    |
| `public.refreshtoken`| `refreshtoken`           | 1:1                                    |
| `public.manga`       | `manga`                  | 1:1                                    |
| `public.chapter`     | `chapter`                | 1:1                                    |
| `public.ocr_result`  | `ocr_result`             | 1:1                                    |
| `public.readhistory` | `readhistory`            | 1:1                                    |
| `public.transcript`  | `transcript`             | gains `individual_settings` (NULL)     |
| `public.transcriptionhistory` | `transcriptionhistory` | gains 5 columns, backfilled from transcript |
| `public.videoprogress` | `videoprogress`        | gains `original_source` ('Youtube')    |

## What is NOT migrated

- **Flashcard data** (per request): `deck`, `card`, `srscard`, `reviewlog`.
  The runner always excludes these.
- **Unused tables** (no current model): `word`, `kanji`, `wordkanjireading`.
- **Supabase system schemas**: `auth`, `storage`, `realtime`, `extensions`,
  `graphql`, `vault`, `pgbouncer`. Only `public` tables are staged.

## How it works

1. `run_migration.py` reads `migrate.toml`.
2. The old data is staged into a scratch schema (`legacy_2026` by default) so
   the full Supabase dump never collides with the live tables. When a SQL file
   is the source, only `public` tables are loaded (system schemas stripped).
3. Each `NN_*.sql` step is executed with `:staging` substituted by the staging
   schema name. Steps use `WHERE NOT EXISTS` guards, so re-running is safe.
4. On success the staging schema is dropped (unless
   `drop_staging_on_success = false`).

## Running locally

```bash
# Uses DATABASE_URL-equivalent target from migrate.toml
python migrations/run_migration.py
```

The script reads the target connection from `migrate.toml` (`[target].url`).

## Running in production

Point the runner at the production database without editing the file:

```bash
MIGRATION_TARGET_URL=postgresql://user:pass@prod-host:5432/prod_db \
MIGRATION_OLD_SQL_PATH=ref/old_db.sql \
python migrations/run_migration.py
```

Or set `target.url` / `source.sql_file` directly in `migrate.toml` for the
deployment. The same script and SQL steps are used; nothing is hardcoded.

## Configuration (`migrate.toml`)

| Key | Meaning |
|-----|---------|
| `source.sql_file` | Path (relative to project root) to the old SQL dump. |
| `source.url` | Alternative: a live old DB to stage from. |
| `target.url` | The current/target application database. |
| `options.staging_schema` | Scratch schema for the staged old data. |
| `options.exclude_tables` | Extra old tables to skip. |
| `options.drop_staging_on_success` | Clean up the staging schema after success. |

Environment overrides (highest precedence): `MIGRATION_TARGET_URL`,
`MIGRATION_SOURCE_URL`, `MIGRATION_OLD_SQL_PATH`.
