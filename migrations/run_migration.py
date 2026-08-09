"""Database migration runner.

Usage
-----
    # run against the database configured in migrations/migrate.toml
    python migrations/run_migration.py

    # override the target (production) database
    MIGRATION_TARGET_URL=postgresql://...:5432/prod_db python migrations/run_migration.py

    # override the source dump file
    MIGRATION_OLD_SQL_PATH=path/to/old_db.sql python migrations/run_migration.py

What it does
------------
1. Loads the old database dump from either a live `source.url` or a SQL file
   (`source.sql_file`). When a file is used, only the `public` schema tables
   are loaded into a scratch schema named by `options.staging_schema`
   (default `legacy_2026`), so the dump's Supabase internals never touch the
   real database.
2. Runs every `NN_*.sql` step in migrations/, substituting `:staging` with the
   staging schema name. Steps are written to be idempotent (WHERE NOT EXISTS),
   so the script is safe to re-run in production.

The excluded tables (word, kanji, wordkanjireading) and flashcard tables
(deck, card, srscard, reviewlog) are intentionally not migrated.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.sql as psql
except ImportError:
    sys.exit("psycopg2 is required. Install it with: pip install psycopg2")

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        sys.exit("tomllib/tomli is required to read the config (Python 3.11+ or `pip install tomli`)")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = MIGRATIONS_DIR / "migrate.toml"

# Old-dump COPY/statement lines we never want to load into the target DB.
# The Supabase system schemas are skipped entirely; only `public` is staged.
SYSTEM_SCHEMAS = {
    "auth", "extensions", "graphql", "graphql_public", "pgbouncer",
    "realtime", "storage", "vault",
}


def log(msg: str) -> None:
    print(f"[migration] {msg}")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"Config not found: {CONFIG_PATH}")
    with CONFIG_PATH.open("rb") as f:
        cfg = tomllib.load(f)

    # Environment overrides take precedence.
    if os.environ.get("MIGRATION_TARGET_URL"):
        cfg.setdefault("target", {})["url"] = os.environ["MIGRATION_TARGET_URL"]
    if os.environ.get("MIGRATION_SOURCE_URL"):
        cfg.setdefault("source", {})["url"] = os.environ["MIGRATION_SOURCE_URL"]
    if os.environ.get("MIGRATION_OLD_SQL_PATH"):
        cfg.setdefault("source", {})["sql_file"] = os.environ["MIGRATION_OLD_SQL_PATH"]

    if not cfg.get("target", {}).get("url"):
        sys.exit("target.url is not configured (set it in migrate.toml or MIGRATION_TARGET_URL)")
    source = cfg.get("source", {})
    if not source.get("url") and not source.get("sql_file"):
        sys.exit("source.url or source.sql_file must be configured")
    return cfg


def connect(url: str):
    return psycopg2.connect(url)


# ----------------------------------------------------------------------------
# Staging the old dump
# ----------------------------------------------------------------------------

import io

DEFAULT_STAGING = "legacy_2026"

# Matches the `CREATE TABLE [schema.]"table" (` header of a dump statement.
_RE_CREATE = re.compile(r'^CREATE TABLE\s+([\w]+\.)?("?[\w]+"?)\s*\(')
# Matches the `COPY [schema.]"table" (cols) FROM stdin;` header.
_RE_COPY = re.compile(r'^COPY\s+([\w]+\.)?("?[\w]+"?)\s*\((.+)\)\s+FROM stdin;')


def _split_name(schema_part: str | None, table_part: str) -> tuple[str | None, str]:
    table = table_part.strip().strip('"')
    if schema_part:
        schema = schema_part[:-1].strip().strip('"')  # drop trailing dot
        return schema, table
    return None, table


def _staging_table(table: str, staging: str) -> str:
    return f"{staging}.{table}"


def _stage_public_tables_from_dump(cur, dump_path: Path, exclude: set[str], staging: str) -> None:
    """Stream the pg_dump file and stage only public tables into `staging`.

    DDL is executed directly. ``COPY ... FROM stdin`` blocks are streamed with
    psycopg2's copy_expert (which understands the COPY protocol), so even very
    large tables load correctly. System schemas and excluded tables are skipped.
    """
    cur.execute(psql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(psql.Identifier(staging)))
    cur.execute(psql.SQL("CREATE SCHEMA {}").format(psql.Identifier(staging)))

    with dump_path.open("r", encoding="utf-8") as f:
        pending_ddl: list[str] = []          # buffered DDL lines for one CREATE TABLE
        in_create = False
        create_keep = False
        create_depth = 0                     # parenthesis depth inside CREATE TABLE
        copy_table = None
        copy_cols: list[str] = []
        copy_data: list[str] = []

        def flush_ddl() -> None:
            nonlocal pending_ddl, in_create, create_keep, create_depth
            if pending_ddl:
                stmt = "\n".join(pending_ddl).strip()
                if create_keep and stmt.endswith(";"):
                    cur.execute(stmt)
            pending_ddl = []
            in_create = False
            create_keep = False
            create_depth = 0

        def flush_copy() -> None:
            nonlocal copy_table, copy_cols, copy_data
            if copy_table is not None and copy_table not in exclude and copy_data:
                dst = _staging_table(copy_table, staging)
                sql = f"COPY {dst} ({', '.join(copy_cols)}) FROM STDIN WITH (FORMAT text)"
                cur.copy_expert(sql, io.StringIO("\n".join(copy_data) + "\n"))
            copy_table = None
            copy_cols = []
            copy_data = []

        for raw in f:
            line = raw.rstrip("\n")
            low = line.lower().strip()

            if in_create:
                # Track parenthesis depth so we stop at the matching ');'
                create_depth += line.count("(") - line.count(")")
                pending_ddl.append(line)
                if create_depth <= 0 and low.endswith(";"):
                    flush_ddl()
                continue

            if copy_table is not None:
                if low == "\\.":
                    flush_copy()
                else:
                    copy_data.append(line)
                continue

            m_create = _RE_CREATE.match(line)
            if m_create:
                schema, table = _split_name(m_create.group(1), m_create.group(2))
                in_create = True
                create_keep = (schema in (None, "public")) and table not in exclude
                if create_keep:
                    dst = _staging_table(table, staging)
                    # Rewrite the table name to the staging schema; keep columns.
                    pending_ddl.append(f'CREATE TABLE {dst} (')
                    create_depth = line.count("(") - line.count(")")
                else:
                    pending_ddl.append(line)  # buffered only to find the matching ');'
                    create_depth = line.count("(") - line.count(")")
                continue

            m_copy = _RE_COPY.match(line)
            if m_copy:
                schema, table = _split_name(m_copy.group(1), m_copy.group(2))
                if (schema in (None, "public")) and table not in exclude:
                    copy_table = table
                    copy_cols = [c.strip().strip('"') for c in m_copy.group(3).split(",")]
                    copy_data = []
                continue

            # Any other statement (ALTER TABLE, SET, COMMENT, etc.) outside a
            # CREATE/COPY block is ignored for staging purposes.

        flush_ddl()
        flush_copy()

    cur.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = %s AND table_type = 'BASE TABLE'",
        (staging,),
    )
    n = cur.fetchone()[0]
    log(f"Staging complete in schema '{staging}': {n} tables loaded.")


def stage_from_sql_file(cur, sql_file: Path, exclude: set[str], staging: str) -> None:
    log(f"Staging old dump from file: {sql_file}")
    _stage_public_tables_from_dump(cur, sql_file, exclude, staging)


def stage_from_live_db(src_conn, cur, exclude: set[str], staging: str) -> None:
    log("Staging old schema from live source database")
    cur.execute(psql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(psql.Identifier(staging)))
    cur.execute(psql.SQL("CREATE SCHEMA {}").format(psql.Identifier(staging)))
    src_cur = src_conn.cursor()
    src_cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    )
    tables = [r[0] for r in src_cur.fetchall() if r[0] not in exclude]
    for t in tables:
        cur.execute(
            psql.SQL("CREATE TABLE {dst} AS TABLE {src}")
            .format(dst=psql.Identifier(staging, t), src=psql.Identifier("public", t))
        )
    log(f"Staged {len(tables)} tables into '{staging}'.")


# ----------------------------------------------------------------------------
# Running transform steps
# ----------------------------------------------------------------------------

def run_steps(cur, staging_schema: str) -> None:
    steps = sorted(
        p for p in MIGRATIONS_DIR.glob("*.sql")
        if re.match(r"^\d+_.*\.sql$", p.name)
    )
    if not steps:
        log("No NN_*.sql step files found.")
        return
    for step in steps:
        log(f"Running step: {step.name}")
        sql = step.read_text(encoding="utf-8")
        # Substitute the :staging placeholder with the actual schema name.
        sql = sql.replace(":staging", staging_schema)
        cur.execute(sql)
        log(f"  done: {step.name}")


def main() -> None:
    cfg = load_config()
    target_url = cfg["target"]["url"]
    source = cfg.get("source", {})
    staging_schema = cfg.get("options", {}).get("staging_schema", DEFAULT_STAGING)
    exclude = set(cfg.get("options", {}).get("exclude_tables", []))
    # Flashcard tables are always excluded by request.
    exclude |= {"deck", "card", "srscard", "reviewlog"}

    target_conn = connect(target_url)
    try:
        target_conn.autocommit = False
        cur = target_conn.cursor()
        if source.get("sql_file"):
            stage_from_sql_file(cur, (ROOT / source["sql_file"]).resolve(), exclude, staging_schema)
        else:
            src_conn = connect(source["url"])
            try:
                stage_from_live_db(src_conn, cur, exclude, staging_schema)
            finally:
                src_conn.close()

        run_steps(cur, staging_schema)
        target_conn.commit()
        log("Migration committed successfully.")
    except Exception as e:  # noqa: BLE001
        target_conn.rollback()
        log(f"Migration FAILED, rolled back: {e}")
        sys.exit(1)
    finally:
        target_conn.close()


if __name__ == "__main__":
    main()
