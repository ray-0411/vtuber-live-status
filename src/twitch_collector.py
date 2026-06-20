#!/usr/bin/env python3
"""
Collect Twitch live status and viewer counts.

Usage:
    $env:TWITCH_CLIENT_ID="..."
    $env:TWITCH_CLIENT_SECRET="..."
    python src/twitch_collector.py
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from streamer_tables import Streamer, read_live_streamers
from time_utils import iso_to_db_time, now_db_time
from working_log import fail_job, finish_job, start_job


DEFAULT_DATABASE = "live_data.db"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
STREAMS_URL = "https://api.twitch.tv/helix/streams"
MAX_LOGINS_PER_REQUEST = 100


@dataclass(frozen=True)
class TwitchStream:
    platform_stream_id: str
    user_login: str
    user_name: str
    title: str
    viewer_count: int
    started_at: str | None
    category: str | None
    tags: list[str]


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers or {},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        return json.loads(body), dict(response.headers)


def get_app_access_token(client_id: str, client_secret: str) -> str:
    payload = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")

    data, _headers = request_json(
        TOKEN_URL,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
    )
    return data["access_token"]


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def fetch_twitch_streams(
    client_id: str,
    access_token: str,
    logins: list[str],
) -> tuple[dict[str, TwitchStream], dict[str, str]]:
    live_by_login: dict[str, TwitchStream] = {}
    latest_headers: dict[str, str] = {}

    for login_chunk in chunked(logins, MAX_LOGINS_PER_REQUEST):
        params = [("user_login", login) for login in login_chunk]
        url = f"{STREAMS_URL}?{urllib.parse.urlencode(params)}"
        data, headers = request_json(
            url,
            headers={
                "Client-Id": client_id,
                "Authorization": f"Bearer {access_token}",
            },
        )
        latest_headers = headers

        for item in data.get("data", []):
            login = item["user_login"].lower()
            live_by_login[login] = TwitchStream(
                platform_stream_id=item["id"],
                user_login=login,
                user_name=item.get("user_name") or item["user_login"],
                title=item.get("title") or "",
                viewer_count=int(item.get("viewer_count") or 0),
                started_at=iso_to_db_time(item.get("started_at")),
                category=item.get("game_name") or item.get("game_id"),
                tags=item.get("tags") or [],
            )

    return live_by_login, latest_headers


def get_twitch_streamers(conn: sqlite3.Connection) -> list[Streamer]:
    return [
        streamer
        for streamer in read_live_streamers(conn, enabled_only=True)
        if streamer.twitch_login
    ]


def upsert_stream(conn: sqlite3.Connection, streamer: Streamer, stream: TwitchStream) -> int:
    stream_url = f"https://www.twitch.tv/{stream.user_login}"
    tags_json = json.dumps(stream.tags, ensure_ascii=False)
    current_time = now_db_time()

    row = conn.execute(
        """
        SELECT stream_id
        FROM stream
        WHERE platform = 'twitch'
          AND platform_stream_id = ?
        """,
        (stream.platform_stream_id,),
    ).fetchone()
    if row is not None:
        stream_id = int(row[0])
        conn.execute(
            """
            UPDATE stream
            SET stream_url = ?,
                title = ?,
                category = ?,
                tags = ?,
                started_at = ?,
                last_seen_at = ?,
                updated_at = ?
            WHERE stream_id = ?
            """,
            (
                stream_url,
                stream.title,
                stream.category,
                tags_json,
                stream.started_at,
                current_time,
                current_time,
                stream_id,
            ),
        )
        return stream_id

    conn.execute(
        """
        INSERT INTO stream (
            vtuber_id,
            platform,
            platform_stream_id,
            stream_url,
            title,
            category,
            tags,
            started_at,
            first_seen_at,
            last_seen_at,
            created_at,
            updated_at
        )
        VALUES (?, 'twitch', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            streamer.vtuber_id,
            stream.platform_stream_id,
            stream_url,
            stream.title,
            stream.category,
            tags_json,
            stream.started_at,
            current_time,
            current_time,
            current_time,
            current_time,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def insert_snapshot(
    conn: sqlite3.Connection,
    stream_id: int,
    streamer: Streamer,
    stream: TwitchStream,
) -> None:
    current_time = now_db_time()
    conn.execute(
        """
        INSERT INTO stream_snapshot (
            stream_id,
            vtuber_id,
            platform,
            viewer_count,
            captured_at,
            title,
            category,
            tags
        )
        VALUES (?, ?, 'twitch', ?, ?, ?, ?, ?)
        """,
        (
            stream_id,
            streamer.vtuber_id,
            stream.viewer_count,
            current_time,
            stream.title,
            stream.category,
            json.dumps(stream.tags, ensure_ascii=False),
        ),
    )


def update_live_status(
    conn: sqlite3.Connection,
    streamer: Streamer,
    stream_id: int,
    stream: TwitchStream,
) -> None:
    current_time = now_db_time()
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
            category,
            tags,
            started_at,
            last_checked_at,
            last_live_at
        )
        VALUES (?, 'twitch', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(vtuber_id, platform) DO UPDATE SET
            is_live = 1,
            stream_id = excluded.stream_id,
            viewer_count = excluded.viewer_count,
            stream_url = excluded.stream_url,
            title = excluded.title,
            category = excluded.category,
            tags = excluded.tags,
            started_at = excluded.started_at,
            last_checked_at = excluded.last_checked_at,
            last_live_at = excluded.last_live_at
        """,
        (
            streamer.vtuber_id,
            stream_id,
            stream.viewer_count,
            f"https://www.twitch.tv/{stream.user_login}",
            stream.title,
            stream.category,
            json.dumps(stream.tags, ensure_ascii=False),
            stream.started_at,
            current_time,
            current_time,
        ),
    )


def update_offline_status(conn: sqlite3.Connection, streamer: Streamer) -> None:
    current_time = now_db_time()
    conn.execute(
        """
        INSERT INTO current_live_status (
            vtuber_id,
            platform,
            is_live,
            last_checked_at
        )
        VALUES (?, 'twitch', 0, ?)
        ON CONFLICT(vtuber_id, platform) DO UPDATE SET
            is_live = 0,
            last_checked_at = excluded.last_checked_at
        """,
        (streamer.vtuber_id, current_time),
    )


def collect_twitch(database: str, client_id: str, client_secret: str) -> dict[str, Any]:
    started = time.perf_counter()
    working_id: int | None = None

    try:
        with sqlite3.connect(database) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            working_id = start_job(conn, "twitch_collector", "twitch")
            streamers = get_twitch_streamers(conn)

        logins = sorted({streamer.twitch_login.lower() for streamer in streamers if streamer.twitch_login})
        access_token = get_app_access_token(client_id, client_secret)
        live_by_login, headers = fetch_twitch_streams(client_id, access_token, logins)

        snapshots_inserted = 0
        with sqlite3.connect(database) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            for streamer in streamers:
                login = streamer.twitch_login.lower() if streamer.twitch_login else ""
                stream = live_by_login.get(login)
                if stream is None:
                    update_offline_status(conn, streamer)
                    continue

                stream_id = upsert_stream(conn, streamer, stream)
                insert_snapshot(conn, stream_id, streamer, stream)
                update_live_status(conn, streamer, stream_id, stream)
                snapshots_inserted += 1

            elapsed = time.perf_counter() - started
            summary = {
                "checked": len(streamers),
                "live": len(live_by_login),
                "offline": len(streamers) - len(live_by_login),
                "snapshots_inserted": snapshots_inserted,
                "elapsed_seconds": elapsed,
                "rate_limit_remaining": headers.get("Ratelimit-Remaining"),
                "rate_limit_limit": headers.get("Ratelimit-Limit"),
            }
            if working_id is not None:
                finish_job(
                    conn,
                    working_id,
                    status="success",
                    elapsed_seconds=elapsed,
                    checked_count=summary["checked"],
                    live_count=summary["live"],
                    offline_count=summary["offline"],
                    snapshots_inserted=summary["snapshots_inserted"],
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

    parser = argparse.ArgumentParser(description="Collect Twitch live status.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    args = parser.parse_args()

    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET.", file=sys.stderr)
        return 1

    summary = collect_twitch(args.database, client_id, client_secret)
    print(
        "checked={checked} live={live} offline={offline} "
        "snapshots_inserted={snapshots_inserted} elapsed_seconds={elapsed_seconds:.2f}".format(
            **summary
        )
    )
    if summary["rate_limit_remaining"] and summary["rate_limit_limit"]:
        print(
            "rate_limit="
            f"{summary['rate_limit_remaining']}/{summary['rate_limit_limit']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
