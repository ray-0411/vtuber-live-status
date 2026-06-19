#!/usr/bin/env python3
"""
List streamer rows from all streamer_* tables.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from streamer_tables import read_live_streamers


DEFAULT_DATABASE = "live_data.db"


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="List streamers from streamer_* tables.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--all", action="store_true", help="Include disabled rows.")
    args = parser.parse_args()

    with sqlite3.connect(args.database) as conn:
        streamers = read_live_streamers(conn, enabled_only=not args.all)

    print(f"streamers={len(streamers)}")
    for streamer in streamers:
        platforms = []
        if streamer.youtube_url or streamer.youtube_channel_id:
            platforms.append("youtube")
        if streamer.twitch_url or streamer.twitch_login:
            platforms.append("twitch")
        platform_text = ",".join(platforms) if platforms else "-"
        print(
            f"{streamer.group_name:<12} {streamer.vtuber_id:<16} "
            f"{streamer.name:<16} enabled={streamer.enabled} platforms={platform_text}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
