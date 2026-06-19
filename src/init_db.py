#!/usr/bin/env python3
"""
Initialize the project SQLite database.

Usage:
    python src/init_db.py
    python src/init_db.py --database live_data.db
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DEFAULT_DATABASE = "live_data.db"
CORE_SQL_FILES = [
    "002_streamer.sql",
    "010_stream.sql",
    "011_stream_snapshot.sql",
    "012_current_live_status.sql",
    "013_working.sql",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_sql_file(conn: sqlite3.Connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    conn.executescript(sql)


def init_core_tables(database: str) -> list[str]:
    sql_dir = project_root() / "sql_init"
    executed: list[str] = []

    with sqlite3.connect(database) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for file_name in CORE_SQL_FILES:
            run_sql_file(conn, sql_dir / file_name)
            executed.append(file_name)

    return executed


def init_database(database: str) -> list[str]:
    sql_files = init_core_tables(database)
    return sql_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize project database tables.")
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE,
        help=f"SQLite database path. Default: {DEFAULT_DATABASE}",
    )
    args = parser.parse_args()

    sql_files = init_database(args.database)

    print(f"Database: {args.database}")
    print("Initialized core SQL:")
    for file_name in sql_files:
        print(f"- {file_name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
