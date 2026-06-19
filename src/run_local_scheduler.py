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
import json
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from collect_all import DEFAULT_CONFIG_DATABASE, DEFAULT_DATABASE, collect_all
from init_db import init_database
from init_streamer_config import DEFAULT_GROUPS
from create_streamer_group import create_streamer_group


DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_TIMEZONE = "Asia/Taipei"


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def now_text(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).isoformat(timespec="seconds")


def initialize_databases(database: str, config_database: str) -> None:
    init_database(database)
    for group in DEFAULT_GROUPS:
        create_streamer_group(config_database, group)


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

    if summary["errors"]:
        print(json.dumps(summary["errors"], ensure_ascii=False, indent=2), file=sys.stderr)

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
        "--skip-init",
        action="store_true",
        help="Do not initialize database schemas before collecting.",
    )
    args = parser.parse_args()

    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be greater than 0")

    if not args.skip_init:
        initialize_databases(args.database, args.config_database)

    exit_code = 0
    while True:
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

        if args.once:
            return exit_code

        print(
            f"[{now_text(args.timezone)}] sleep {args.interval_seconds} seconds",
            flush=True,
        )
        try:
            time.sleep(args.interval_seconds)
        except KeyboardInterrupt:
            print(f"[{now_text(args.timezone)}] stopped by user", flush=True)
            return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
