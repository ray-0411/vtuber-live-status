#!/usr/bin/env python3
"""
Fill missing youtube_channel_id values in streamer config tables.

Usage:
    python src/backfill_youtube_channel_ids.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from streamer_tables import list_streamer_tables
from time_utils import now_db_time
from youtube_utils import fetch_youtube_channel_id


DEFAULT_DATABASE = "streamer_config.db"


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def backfill_youtube_channel_ids(database: str, dry_run: bool = False) -> dict[str, int]:
    checked = 0
    updated = 0
    failed = 0

    with sqlite3.connect(database) as conn:
        for table_name in list_streamer_tables(conn):
            rows = conn.execute(
                f"""
                SELECT vtuber_id, name, youtube_url
                FROM {table_name}
                WHERE youtube_url IS NOT NULL
                  AND youtube_url != ''
                  AND (youtube_channel_id IS NULL OR youtube_channel_id = '')
                ORDER BY COALESCE(display_order, 999999), vtuber_id
                """
            ).fetchall()

            for vtuber_id, name, youtube_url in rows:
                checked += 1
                try:
                    youtube_channel_id = fetch_youtube_channel_id(youtube_url)
                except Exception as exc:
                    failed += 1
                    print(
                        f"failed {table_name}.{vtuber_id}: {type(exc).__name__}: {exc}",
                        file=sys.stderr,
                    )
                    continue

                if not youtube_channel_id:
                    failed += 1
                    print(f"failed {table_name}.{vtuber_id}: no channel id found", file=sys.stderr)
                    continue

                print(f"{table_name}.{vtuber_id} {name}: {youtube_channel_id}")
                if not dry_run:
                    conn.execute(
                        f"""
                        UPDATE {table_name}
                        SET youtube_channel_id = ?,
                            updated_at = ?
                        WHERE vtuber_id = ?
                        """,
                        (youtube_channel_id, now_db_time(), vtuber_id),
                    )
                updated += 1

    return {"checked": checked, "updated": updated, "failed": failed}


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Fill missing YouTube channel ids.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--dry-run", action="store_true", help="Print matches without updating.")
    args = parser.parse_args()

    summary = backfill_youtube_channel_ids(args.database, dry_run=args.dry_run)
    print(
        "checked={checked} updated={updated} failed={failed}".format(
            **summary,
        )
    )
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
