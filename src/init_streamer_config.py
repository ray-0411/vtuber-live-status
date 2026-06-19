#!/usr/bin/env python3
"""
Initialize the streamer config database.

Usage:
    python src/init_streamer_config.py
    python src/init_streamer_config.py --database streamer_config.db --group meridian --group squarelive
"""

from __future__ import annotations

import argparse

from create_streamer_group import create_streamer_group


DEFAULT_DATABASE = "streamer_config.db"
DEFAULT_GROUPS = ["meridian", "squarelive"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize streamer config database.")
    parser.add_argument(
        "--database",
        default=DEFAULT_DATABASE,
        help=f"SQLite database path. Default: {DEFAULT_DATABASE}",
    )
    parser.add_argument(
        "--group",
        action="append",
        dest="groups",
        help="Streamer group name. Can be passed multiple times.",
    )
    args = parser.parse_args()

    groups = args.groups if args.groups is not None else DEFAULT_GROUPS
    tables = [create_streamer_group(args.database, group) for group in groups]

    print(f"Database: {args.database}")
    print("Initialized streamer config tables:")
    for table_name in tables:
        print(f"- {table_name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
