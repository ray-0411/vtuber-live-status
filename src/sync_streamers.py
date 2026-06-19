#!/usr/bin/env python3
"""
Sync streamer config tables into live_data.db streamer table.

Usage:
    python src/sync_streamers.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from streamer_tables import Streamer, read_streamers
from time_utils import now_db_time


DEFAULT_CONFIG_DATABASE = "streamer_config.db"
DEFAULT_LIVE_DATABASE = "live_data.db"


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def find_duplicate_ids(streamers: list[Streamer]) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for streamer in streamers:
        seen.setdefault(streamer.vtuber_id, []).append(streamer.table_name)
    return {vtuber_id: tables for vtuber_id, tables in seen.items() if len(tables) > 1}


def sync_streamers(config_database: str, live_database: str) -> int:
    with sqlite3.connect(config_database) as config_conn:
        streamers = read_streamers(config_conn, enabled_only=False)

    duplicates = find_duplicate_ids(streamers)
    if duplicates:
        details = "; ".join(
            f"{vtuber_id}: {', '.join(tables)}"
            for vtuber_id, tables in sorted(duplicates.items())
        )
        raise ValueError(f"Duplicate vtuber_id found: {details}")

    with sqlite3.connect(live_database) as live_conn:
        current_time = now_db_time()
        live_conn.execute("DELETE FROM streamer")
        live_conn.executemany(
            """
            INSERT INTO streamer (
                vtuber_id,
                group_name,
                name,
                youtube_url,
                youtube_channel_id,
                twitch_url,
                twitch_login,
                enabled,
                display_order,
                note,
                synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    streamer.vtuber_id,
                    streamer.group_name,
                    streamer.name,
                    streamer.youtube_url,
                    streamer.youtube_channel_id,
                    streamer.twitch_url,
                    streamer.twitch_login,
                    streamer.enabled,
                    streamer.display_order,
                    streamer.note,
                    current_time,
                )
                for streamer in streamers
            ],
        )

    return len(streamers)


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Sync streamer config into live database.")
    parser.add_argument("--config-database", default=DEFAULT_CONFIG_DATABASE)
    parser.add_argument("--live-database", default=DEFAULT_LIVE_DATABASE)
    args = parser.parse_args()

    count = sync_streamers(args.config_database, args.live_database)
    print(f"Synced streamers: {count}")
    print(f"Config database: {args.config_database}")
    print(f"Live database: {args.live_database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
