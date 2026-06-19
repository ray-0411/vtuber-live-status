#!/usr/bin/env python3
"""
Add or update one streamer row in a streamer group table.

Usage:
    python src/add_streamer.py meridian rei "澪Rei" --youtube-url URL --twitch-login reirei_neon
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from streamer_tables import table_name_for_group
from time_utils import now_db_time


DEFAULT_DATABASE = "streamer_config.db"


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def add_streamer(
    database: str,
    group_name: str,
    vtuber_id: str,
    name: str,
    youtube_url: str | None,
    youtube_channel_id: str | None,
    twitch_url: str | None,
    twitch_login: str | None,
    enabled: int,
    display_order: int | None,
    note: str | None,
) -> str:
    table_name = table_name_for_group(group_name)
    with sqlite3.connect(database) as conn:
        current_time = now_db_time()
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        if not exists:
            raise ValueError(f"Table does not exist: {table_name}")

        conn.execute(
            f"""
            INSERT INTO {table_name} (
                vtuber_id,
                name,
                youtube_url,
                youtube_channel_id,
                twitch_url,
                twitch_login,
                enabled,
                display_order,
                note,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vtuber_id) DO UPDATE SET
                name = excluded.name,
                youtube_url = excluded.youtube_url,
                youtube_channel_id = excluded.youtube_channel_id,
                twitch_url = excluded.twitch_url,
                twitch_login = excluded.twitch_login,
                enabled = excluded.enabled,
                display_order = excluded.display_order,
                note = excluded.note,
                updated_at = excluded.updated_at
            """,
            (
                vtuber_id,
                name,
                youtube_url,
                youtube_channel_id,
                twitch_url,
                twitch_login,
                enabled,
                display_order,
                note,
                current_time,
                current_time,
            ),
        )

    return table_name


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Add or update a streamer.")
    parser.add_argument("group_name", help="Group table suffix, e.g. meridian.")
    parser.add_argument("vtuber_id", help="Unique VTuber id.")
    parser.add_argument("name", help="VTuber display name.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--youtube-url")
    parser.add_argument("--youtube-channel-id")
    parser.add_argument("--twitch-url")
    parser.add_argument("--twitch-login")
    parser.add_argument("--disabled", action="store_true", help="Insert as enabled = 0.")
    parser.add_argument("--display-order", type=int)
    parser.add_argument("--note")
    args = parser.parse_args()

    table_name = add_streamer(
        database=args.database,
        group_name=args.group_name,
        vtuber_id=args.vtuber_id,
        name=args.name,
        youtube_url=args.youtube_url,
        youtube_channel_id=args.youtube_channel_id,
        twitch_url=args.twitch_url,
        twitch_login=args.twitch_login,
        enabled=0 if args.disabled else 1,
        display_order=args.display_order,
        note=args.note,
    )

    print(f"Added or updated {args.vtuber_id} in {table_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
