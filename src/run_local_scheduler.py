#!/usr/bin/env python3
"""
Run the live-status collector repeatedly on a local machine.

Usage:
    python src/run_local_scheduler.py
    python src/run_local_scheduler.py --once
    python src/run_local_scheduler.py --interval-seconds 300
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from collect_all import DEFAULT_CONFIG_DATABASE, DEFAULT_DATABASE, collect_all
from init_db import init_database
from init_streamer_config import DEFAULT_GROUPS
from create_streamer_group import create_streamer_group


DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_TIMEZONE = "Asia/Taipei"


@dataclass(frozen=True)
class LiveStatusRow:
    platform: str
    vtuber_id: str
    name: str
    viewer_count: int | None
    title: str | None
    stream_url: str | None


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def now_text(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).isoformat(timespec="seconds")


def next_run_time(timezone_name: str, interval_seconds: int) -> datetime:
    zone = ZoneInfo(timezone_name)
    now = datetime.now(zone)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed_seconds = (now - day_start).total_seconds()
    next_elapsed = ((int(elapsed_seconds) // interval_seconds) + 1) * interval_seconds
    return day_start + timedelta(seconds=next_elapsed)


def seconds_until(target: datetime) -> float:
    return max(0.0, (target - datetime.now(target.tzinfo)).total_seconds())


def initialize_databases(database: str, config_database: str) -> None:
    init_database(database)
    for group in DEFAULT_GROUPS:
        create_streamer_group(config_database, group)


def read_current_lives(database: str) -> list[LiveStatusRow]:
    with sqlite3.connect(database) as conn:
        rows = conn.execute(
            """
            SELECT
                current_live_status.platform,
                current_live_status.vtuber_id,
                streamer.name,
                current_live_status.viewer_count,
                current_live_status.title,
                current_live_status.stream_url
            FROM current_live_status
            JOIN streamer
              ON streamer.vtuber_id = current_live_status.vtuber_id
            WHERE current_live_status.is_live = 1
            ORDER BY current_live_status.platform, streamer.group_name, streamer.display_order
            """
        ).fetchall()

    return [
        LiveStatusRow(
            platform=row[0],
            vtuber_id=row[1],
            name=row[2],
            viewer_count=row[3],
            title=row[4],
            stream_url=row[5],
        )
        for row in rows
    ]


def print_live_report(database: str) -> None:
    lives = read_current_lives(database)
    by_platform = {
        "youtube": [live for live in lives if live.platform == "youtube"],
        "twitch": [live for live in lives if live.platform == "twitch"],
    }

    print("", flush=True)
    for platform, platform_lives in by_platform.items():
        print(f"{platform.upper()} live: {len(platform_lives)}", flush=True)
        if not platform_lives:
            print("- none", flush=True)
            continue

        for live in platform_lives:
            viewer_text = "unknown" if live.viewer_count is None else str(live.viewer_count)
            print(f"- {live.name}: {viewer_text}", flush=True)

    print(f"TOTAL live now: {len(lives)}", flush=True)


def print_error_report(summary: dict[str, object]) -> None:
    errors: list[str] = []

    top_level_errors = summary.get("errors", [])
    if isinstance(top_level_errors, list):
        errors.extend(str(error) for error in top_level_errors)

    results = summary.get("results", {})
    if isinstance(results, dict):
        for platform, result in results.items():
            if not isinstance(result, dict):
                continue
            platform_errors = result.get("errors", [])
            if isinstance(platform_errors, list):
                errors.extend(f"{platform}: {error}" for error in platform_errors)

    print("", flush=True)
    if not errors:
        print("ERRORS: none", flush=True)
        return

    print(f"ERRORS: {len(errors)}", flush=True)
    for error in errors:
        print(f"- {error}", flush=True)


def run_once(database: str, config_database: str, timezone_name: str) -> int:
    started = time.perf_counter()
    print(f"[{now_text(timezone_name)}] collect start", flush=True)
    summary = collect_all(database, config_database)
    elapsed = time.perf_counter() - started

    print(
        "[{time}] collect done status={status} checked={checked} live={live} "
        "offline={offline} snapshots_inserted={snapshots_inserted} "
        "synced_streamers={synced_streamers} errors={errors} elapsed_seconds={elapsed:.2f}".format(
            time=now_text(timezone_name),
            status=summary["status"],
            checked=summary["checked"],
            live=summary["live"],
            offline=summary["offline"],
            snapshots_inserted=summary["snapshots_inserted"],
            synced_streamers=summary["synced_streamers"],
            errors=len(summary["errors"]),
            elapsed=elapsed,
        ),
        flush=True,
    )

    print_live_report(database)
    print_error_report(summary)
    return 0 if summary["status"] in {"success", "partial_success"} else 1


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Run collect_all repeatedly on this machine.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--config-database", default=DEFAULT_CONFIG_DATABASE)
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--once", action="store_true", help="Run one collection and exit.")
    parser.add_argument(
        "--run-immediately",
        action="store_true",
        help="Run once immediately, then continue on the aligned schedule.",
    )
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="Do not initialize database schemas before collecting.",
    )
    args = parser.parse_args()

    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be greater than 0")

    if not args.skip_init:
        initialize_databases(args.database, args.config_database)

    print(
        f"[{now_text(args.timezone)}] scheduler timezone={args.timezone} "
        f"interval_seconds={args.interval_seconds} aligned=true",
        flush=True,
    )

    exit_code = 0
    should_run_now = args.once or args.run_immediately
    while True:
        if should_run_now:
            try:
                exit_code = max(exit_code, run_once(args.database, args.config_database, args.timezone))
            except KeyboardInterrupt:
                print(f"[{now_text(args.timezone)}] stopped by user", flush=True)
                return exit_code
            except Exception as exc:
                exit_code = 1
                print(
                    f"[{now_text(args.timezone)}] collect failed {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                traceback.print_exc()

            if args.once:
                return exit_code

        target = next_run_time(args.timezone, args.interval_seconds)
        sleep_seconds = seconds_until(target)
        print(
            f"[{now_text(args.timezone)}] next run at "
            f"{target.isoformat(timespec='seconds')} sleep {sleep_seconds:.0f} seconds",
            flush=True,
        )
        try:
            time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            print(f"[{now_text(args.timezone)}] stopped by user", flush=True)
            return exit_code
        should_run_now = True


if __name__ == "__main__":
    raise SystemExit(main())
