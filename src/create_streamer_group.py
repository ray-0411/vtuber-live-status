#!/usr/bin/env python3
"""
Create a streamer group table.

Usage:
    python src/create_streamer_group.py meridian
    python src/create_streamer_group.py teraz --database streamer_config.db
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path


DEFAULT_DATABASE = "streamer_config.db"
GROUP_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_group_name(group_name: str) -> str:
    group_name = group_name.strip().lower()
    if not GROUP_NAME_PATTERN.fullmatch(group_name):
        raise ValueError(
            "Group name must start with a lowercase letter and contain only "
            "lowercase letters, numbers, and underscores."
        )
    return group_name


def load_template() -> str:
    root = Path(__file__).resolve().parents[1]
    template_path = root / "sql_init" / "001_streamer_template.sql"
    return template_path.read_text(encoding="utf-8")


def create_streamer_group(database: str, group_name: str) -> str:
    group_name = validate_group_name(group_name)
    table_name = f"streamer_{group_name}"
    sql = load_template().replace("streamer_GROUP_NAME", table_name)

    with sqlite3.connect(database) as conn:
        conn.executescript(sql)

    return table_name


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a streamer group table.")
    parser.add_argument("group_name", help="Group name used in streamer_<group_name>.")
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE,
        help=f"SQLite database path. Default: {DEFAULT_DATABASE}",
    )
    args = parser.parse_args()

    table_name = create_streamer_group(args.database, args.group_name)
    print(f"Created or verified table: {table_name}")
    print(f"Database: {args.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
