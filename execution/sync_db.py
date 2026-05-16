#!/usr/bin/env python3
"""Sync Postgres data between local (Docker) and Railway production.

Usage:
    python execution/sync_db.py local-to-prod          # Push local data to Railway
    python execution/sync_db.py prod-to-local          # Pull production data to local
    python execution/sync_db.py local-to-prod --dry-run # Preview without changes
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

LOCAL_DB = {
    "host": "localhost",
    "port": "5432",
    "user": "postgres",
    "password": "postgres",
    "dbname": "stockanalyzer",
    "container": "stock-analyzer-db-1",
}

TABLES = [
    "stocks",
    "screening_runs",
    "screening_results",
    "research_reports",
    "task_status",
    "portfolio_preferences",
]

DUMP_FILE = PROJECT_ROOT / ".tmp" / "db_sync.sql"


def _error_exit(code: str, message: str) -> None:
    print(json.dumps({"status": "error", "error_code": code, "message": message}))
    sys.exit(1)


def _get_prod_url() -> str:
    """Get production DATABASE_PUBLIC_URL from Railway CLI."""
    try:
        result = subprocess.run(
            ["railway", "variable", "list", "--service", "Postgres", "--json"],
            capture_output=True, text=True, check=True,
            cwd=str(PROJECT_ROOT),
        )
        data = json.loads(result.stdout)
        url = data.get("DATABASE_PUBLIC_URL")
        if not url:
            _error_exit("no_prod_url", "DATABASE_PUBLIC_URL not found in Railway Postgres variables")
        return url
    except FileNotFoundError:
        _error_exit("railway_missing", "Railway CLI not installed. Run: brew install railway")
    except subprocess.CalledProcessError as e:
        _error_exit("railway_error", f"Failed to get Railway variables: {e.stderr}")
    return ""


def _count_rows_local(table: str) -> int:
    result = subprocess.run(
        ["docker", "exec", LOCAL_DB["container"], "psql",
         "-U", LOCAL_DB["user"], "-d", LOCAL_DB["dbname"],
         "-t", "-c", f"SELECT count(*) FROM {table}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return -1
    return int(result.stdout.strip())


def _count_rows_prod(prod_url: str, table: str) -> int:
    result = subprocess.run(
        ["psql", prod_url, "-t", "-c", f"SELECT count(*) FROM {table}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return -1
    return int(result.stdout.strip())


def _dump_local() -> Path:
    """Dump local database data using docker exec pg_dump."""
    DUMP_FILE.parent.mkdir(parents=True, exist_ok=True)
    table_args = []
    for t in TABLES:
        table_args.extend(["-t", t])

    result = subprocess.run(
        ["docker", "exec", LOCAL_DB["container"], "pg_dump",
         "-U", LOCAL_DB["user"], "-d", LOCAL_DB["dbname"],
         "--data-only", "--inserts", "--on-conflict-do-nothing",
         *table_args],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _error_exit("dump_failed", f"pg_dump failed: {result.stderr}")

    DUMP_FILE.write_text(result.stdout)
    log.info("Dumped local data to %s (%d bytes)", DUMP_FILE, len(result.stdout))
    return DUMP_FILE


def _dump_prod(prod_url: str) -> Path:
    """Dump production database data using pg_dump."""
    DUMP_FILE.parent.mkdir(parents=True, exist_ok=True)
    table_args = []
    for t in TABLES:
        table_args.extend(["-t", t])

    result = subprocess.run(
        ["pg_dump", prod_url,
         "--data-only", "--inserts", "--on-conflict-do-nothing",
         *table_args],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _error_exit("dump_failed", f"pg_dump failed: {result.stderr}")

    DUMP_FILE.write_text(result.stdout)
    log.info("Dumped production data to %s (%d bytes)", DUMP_FILE, len(result.stdout))
    return DUMP_FILE


def _restore_to_prod(prod_url: str, dump_file: Path) -> None:
    """Restore dump to production Postgres."""
    result = subprocess.run(
        ["psql", prod_url, "-f", str(dump_file)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 and "ERROR" in result.stderr:
        log.warning("Some errors during restore (may be expected for existing data):\n%s", result.stderr[:500])
    log.info("Restored data to production")


def _restore_to_local(dump_file: Path) -> None:
    """Restore dump to local Docker Postgres."""
    sql = dump_file.read_text()
    result = subprocess.run(
        ["docker", "exec", "-i", LOCAL_DB["container"], "psql",
         "-U", LOCAL_DB["user"], "-d", LOCAL_DB["dbname"]],
        input=sql, capture_output=True, text=True,
    )
    if result.returncode != 0 and "ERROR" in result.stderr:
        log.warning("Some errors during restore (may be expected for existing data):\n%s", result.stderr[:500])
    log.info("Restored data to local database")


def run(args: argparse.Namespace) -> dict:
    direction = args.direction
    prod_url = _get_prod_url()

    log.info("Direction: %s", direction)
    log.info("Production: %s:***@%s", prod_url.split("@")[0].split("//")[1].split(":")[0], prod_url.split("@")[1] if "@" in prod_url else "unknown")

    if direction == "local-to-prod":
        source_label, target_label = "local", "production"
        count_source = _count_rows_local
        count_target = lambda t: _count_rows_prod(prod_url, t)
    else:
        source_label, target_label = "production", "local"
        count_source = lambda t: _count_rows_prod(prod_url, t)
        count_target = _count_rows_local

    log.info("\n--- Data summary ---")
    summary = []
    for table in TABLES:
        src = count_source(table)
        tgt = count_target(table)
        summary.append({"table": table, f"{source_label}_rows": src, f"{target_label}_rows": tgt})
        log.info("  %-25s %s: %4d  |  %s: %4d", table, source_label, src, target_label, tgt)

    if args.dry_run:
        log.info("\nDry run — no changes made.")
        return {"status": "success", "dry_run": True, "direction": direction, "tables": summary}

    print(f"\nThis will sync data from {source_label} -> {target_label}.")
    print("Existing rows with matching primary keys will be skipped (ON CONFLICT DO NOTHING).")
    confirm = input("Continue? [y/N] ").strip().lower()
    if confirm != "y":
        log.info("Aborted.")
        return {"status": "aborted"}

    if direction == "local-to-prod":
        dump_file = _dump_local()
        _restore_to_prod(prod_url, dump_file)
    else:
        dump_file = _dump_prod(prod_url)
        _restore_to_local(dump_file)

    log.info("\n--- Post-sync counts ---")
    post_summary = []
    for table in TABLES:
        tgt = count_target(table)
        post_summary.append({"table": table, f"{target_label}_rows": tgt})
        log.info("  %-25s %s: %4d", table, target_label, tgt)

    return {"status": "success", "direction": direction, "tables_synced": len(TABLES)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("direction", choices=["local-to-prod", "prod-to-local"], help="Sync direction")
    parser.add_argument("--dry-run", action="store_true", help="Show row counts without syncing")
    args = parser.parse_args()

    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
