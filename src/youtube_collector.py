#!/usr/bin/env python3
"""
Collect YouTube live status and viewer counts using yt-dlp.

Usage:
    python src/youtube_collector.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from typing import Any

import yt_dlp

from streamer_tables import Streamer, read_live_streamers
from working_log import fail_job, finish_job, start_job


DEFAULT_DATABASE = "live_data.db"
YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})")


class YtDlpLogger:
    def __init__(self, debug_enabled: bool = False) -> None:
        self.debug_enabled = debug_enabled

    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        if self.debug_enabled:
            print(f"yt-dlp warning: {message}", file=sys.stderr)

    def error(self, message: str) -> None:
        if self.debug_enabled:
            print(f"yt-dlp error: {message}", file=sys.stderr)


@dataclass(frozen=True)
class YouTubeLiveResult:
    platform_stream_id: str
    stream_url: str
    title: str
    viewer_count: int | None
    started_at: str | None


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def debug_payload(info: dict[str, Any] | None) -> str:
    if not info:
        return "<no info>"
    payload = {
        "id": info.get("id"),
        "title": info.get("title"),
        "is_live": info.get("is_live"),
        "live_status": info.get("live_status"),
        "webpage_url": info.get("webpage_url"),
        "url": info.get("url"),
        "concurrent_view_count": info.get("concurrent_view_count"),
        "release_timestamp": info.get("release_timestamp"),
        "timestamp": info.get("timestamp"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def debug_log(enabled: bool, message: str) -> None:
    if enabled:
        print(message, file=sys.stderr)


def get_youtube_streamers(conn: sqlite3.Connection) -> list[Streamer]:
    return [
        streamer
        for streamer in read_live_streamers(conn, enabled_only=True)
        if streamer.youtube_url
    ]


def normalize_video_url(info: dict[str, Any]) -> str | None:
    url = info.get("webpage_url") or info.get("url")
    if isinstance(url, str) and url.startswith("http"):
        return url

    video_id = info.get("id")
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return None


def extract_video_id(url: str, fallback: str | None = None) -> str | None:
    match = YOUTUBE_VIDEO_ID_PATTERN.search(url)
    if match:
        return match.group(1)
    return fallback


def is_live_info(info: dict[str, Any]) -> bool:
    return info.get("is_live") is True or info.get("live_status") == "is_live"


def unix_timestamp_to_iso(value: Any) -> str | None:
    if not value:
        return None
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(value)))
    except (TypeError, ValueError, OSError):
        return None


def fetch_youtube_live(channel_url: str, debug: bool = False) -> YouTubeLiveResult | None:
    ydl_opts = {
        "quiet": True,
        "no_warnings": not debug,
        "skip_download": True,
        "ignoreerrors": False,
        "logger": YtDlpLogger(debug),
    }

    url = f"{channel_url.rstrip('/')}/live"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as exc:
            debug_log(debug, f"yt-dlp download error for {url}: {type(exc).__name__}: {exc}")
            return None
        except Exception as exc:
            debug_log(debug, f"yt-dlp unexpected error for {url}: {type(exc).__name__}: {exc}")
            return None

    debug_log(debug, f"yt-dlp raw info for {url}: {debug_payload(info)}")

    if not info or not is_live_info(info):
        return None

    stream_url = normalize_video_url(info)
    if not stream_url:
        debug_log(debug, f"yt-dlp live info missing url for {url}")
        return None

    platform_stream_id = extract_video_id(stream_url, fallback=info.get("id"))
    if not platform_stream_id:
        debug_log(debug, f"yt-dlp live info missing video id for {url}")
        return None

    viewer_count = info.get("concurrent_view_count")
    if viewer_count is not None:
        try:
            viewer_count = int(viewer_count)
        except (TypeError, ValueError):
            viewer_count = None

    return YouTubeLiveResult(
        platform_stream_id=platform_stream_id,
        stream_url=stream_url,
        title=info.get("title") or "",
        viewer_count=viewer_count,
        started_at=unix_timestamp_to_iso(info.get("timestamp") or info.get("release_timestamp")),
    )


def upsert_stream(conn: sqlite3.Connection, streamer: Streamer, live: YouTubeLiveResult) -> int:
    conn.execute(
        """
        INSERT INTO stream (
            vtuber_id,
            platform,
            platform_stream_id,
            stream_url,
            title,
            started_at,
            last_seen_at,
            updated_at
        )
        VALUES (?, 'youtube', ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(platform, platform_stream_id) DO UPDATE SET
            stream_url = excluded.stream_url,
            title = excluded.title,
            started_at = excluded.started_at,
            last_seen_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            streamer.vtuber_id,
            live.platform_stream_id,
            live.stream_url,
            live.title,
            live.started_at,
        ),
    )
    row = conn.execute(
        """
        SELECT stream_id
        FROM stream
        WHERE platform = 'youtube'
          AND platform_stream_id = ?
        """,
        (live.platform_stream_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Failed to find stream row: {live.platform_stream_id}")
    return int(row[0])


def insert_snapshot(
    conn: sqlite3.Connection,
    stream_id: int,
    streamer: Streamer,
    live: YouTubeLiveResult,
) -> bool:
    if live.viewer_count is None:
        return False

    conn.execute(
        """
        INSERT INTO stream_snapshot (
            stream_id,
            vtuber_id,
            platform,
            viewer_count,
            title
        )
        VALUES (?, ?, 'youtube', ?, ?)
        """,
        (
            stream_id,
            streamer.vtuber_id,
            live.viewer_count,
            live.title,
        ),
    )
    return True


def update_live_status(
    conn: sqlite3.Connection,
    streamer: Streamer,
    stream_id: int,
    live: YouTubeLiveResult,
) -> None:
    conn.execute(
        """
        INSERT INTO current_live_status (
            vtuber_id,
            platform,
            is_live,
            stream_id,
            viewer_count,
            stream_url,
            title,
            started_at,
            last_checked_at,
            last_live_at
        )
        VALUES (?, 'youtube', 1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(vtuber_id, platform) DO UPDATE SET
            is_live = 1,
            stream_id = excluded.stream_id,
            viewer_count = excluded.viewer_count,
            stream_url = excluded.stream_url,
            title = excluded.title,
            started_at = excluded.started_at,
            last_checked_at = CURRENT_TIMESTAMP,
            last_live_at = CURRENT_TIMESTAMP
        """,
        (
            streamer.vtuber_id,
            stream_id,
            live.viewer_count,
            live.stream_url,
            live.title,
            live.started_at,
        ),
    )


def update_offline_status(conn: sqlite3.Connection, streamer: Streamer) -> None:
    conn.execute(
        """
        INSERT INTO current_live_status (
            vtuber_id,
            platform,
            is_live,
            last_checked_at
        )
        VALUES (?, 'youtube', 0, CURRENT_TIMESTAMP)
        ON CONFLICT(vtuber_id, platform) DO UPDATE SET
            is_live = 0,
            last_checked_at = CURRENT_TIMESTAMP
        """,
        (streamer.vtuber_id,),
    )


def collect_youtube(database: str, debug: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    working_id: int | None = None

    try:
        with sqlite3.connect(database) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            working_id = start_job(conn, "youtube_collector", "youtube")
            streamers = get_youtube_streamers(conn)

        live_count = 0
        snapshots_inserted = 0
        errors: list[str] = []

        with sqlite3.connect(database) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            for streamer in streamers:
                debug_log(
                    debug,
                    f"checking {streamer.vtuber_id} {streamer.youtube_url}",
                )
                try:
                    live = fetch_youtube_live(streamer.youtube_url or "", debug=debug)
                except Exception as exc:
                    errors.append(f"{streamer.vtuber_id}: {type(exc).__name__}: {exc}")
                    update_offline_status(conn, streamer)
                    continue

                if live is None:
                    update_offline_status(conn, streamer)
                    continue

                debug_log(
                    debug,
                    f"live {streamer.vtuber_id} "
                    f"stream_id={live.platform_stream_id} "
                    f"viewer_count={live.viewer_count} "
                    f"title={live.title!r}",
                )
                stream_id = upsert_stream(conn, streamer, live)
                if insert_snapshot(conn, stream_id, streamer, live):
                    snapshots_inserted += 1
                update_live_status(conn, streamer, stream_id, live)
                live_count += 1

            elapsed = time.perf_counter() - started
            summary = {
                "checked": len(streamers),
                "live": live_count,
                "offline": len(streamers) - live_count,
                "snapshots_inserted": snapshots_inserted,
                "errors": errors,
                "elapsed_seconds": elapsed,
            }
            if working_id is not None:
                finish_job(
                    conn,
                    working_id,
                    status="partial_success" if errors else "success",
                    elapsed_seconds=elapsed,
                    checked_count=summary["checked"],
                    live_count=summary["live"],
                    offline_count=summary["offline"],
                    snapshots_inserted=summary["snapshots_inserted"],
                    error_count=len(errors),
                    error_message="\n".join(errors) if errors else None,
                    summary=summary,
                )
            return summary
    except Exception as exc:
        elapsed = time.perf_counter() - started
        error_message = f"{type(exc).__name__}: {exc}"
        if working_id is not None:
            with sqlite3.connect(database) as conn:
                fail_job(
                    conn,
                    working_id,
                    elapsed_seconds=elapsed,
                    error_message=error_message,
                )
        raise


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Collect YouTube live status.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--debug", action="store_true", help="Print yt-dlp response details.")
    args = parser.parse_args()

    debug = args.debug or env_truthy("YOUTUBE_COLLECTOR_DEBUG")
    if debug:
        print("YouTube collector debug mode enabled", file=sys.stderr)

    summary = collect_youtube(args.database, debug=debug)
    print(
        "checked={checked} live={live} offline={offline} "
        "snapshots_inserted={snapshots_inserted} errors={error_count} "
        "elapsed_seconds={elapsed_seconds:.2f}".format(
            error_count=len(summary["errors"]),
            **summary,
        )
    )
    for error in summary["errors"]:
        print(f"ERROR {error}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
