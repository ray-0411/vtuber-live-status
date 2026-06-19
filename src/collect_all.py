#!/usr/bin/env python3
"""
Run all collectors.

Usage:
    $env:TWITCH_CLIENT_ID="..."
    $env:TWITCH_CLIENT_SECRET="..."
    python src/collect_all.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from typing import Any

from twitch_collector import collect_twitch
from sync_streamers import sync_streamers
from working_log import fail_job, finish_job, start_job
from youtube_collector import collect_youtube


DEFAULT_DATABASE = "live_data.db"
DEFAULT_CONFIG_DATABASE = "streamer_config.db"


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def collect_all(database: str, config_database: str) -> dict[str, Any]:
    started = time.perf_counter()
    working_id: int | None = None
    results: dict[str, Any] = {}
    errors: list[str] = []

    with sqlite3.connect(database) as conn:
        working_id = start_job(conn, "collect_all", None)

    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET")
    synced_count = 0

    try:
        synced_count = sync_streamers(config_database, database)
    except Exception as exc:
        errors.append(f"sync_streamers: {type(exc).__name__}: {exc}")

    if client_id and client_secret:
        try:
            results["twitch"] = collect_twitch(database, client_id, client_secret)
        except Exception as exc:
            errors.append(f"twitch: {type(exc).__name__}: {exc}")
    else:
        errors.append("twitch: missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET")

    try:
        results["youtube"] = collect_youtube(database)
    except Exception as exc:
        errors.append(f"youtube: {type(exc).__name__}: {exc}")

    elapsed = time.perf_counter() - started
    checked_count = sum(int(result.get("checked", 0)) for result in results.values())
    live_count = sum(int(result.get("live", 0)) for result in results.values())
    offline_count = sum(int(result.get("offline", 0)) for result in results.values())
    snapshots_inserted = sum(
        int(result.get("snapshots_inserted", 0)) for result in results.values()
    )
    nested_error_count = sum(
        len(result.get("errors", []))
        for result in results.values()
        if isinstance(result.get("errors", []), list)
    )
    error_count = len(errors) + nested_error_count

    if errors and results:
        status = "partial_success"
    elif errors:
        status = "failed"
    elif nested_error_count:
        status = "partial_success"
    else:
        status = "success"

    summary = {
        "checked": checked_count,
        "live": live_count,
        "offline": offline_count,
        "snapshots_inserted": snapshots_inserted,
        "synced_streamers": synced_count,
        "errors": errors,
        "results": results,
        "elapsed_seconds": elapsed,
    }

    with sqlite3.connect(database) as conn:
        if status == "failed":
            fail_job(
                conn,
                working_id,
                elapsed_seconds=elapsed,
                error_message="\n".join(errors),
                summary=summary,
            )
        else:
            finish_job(
                conn,
                working_id,
                status=status,
                elapsed_seconds=elapsed,
                checked_count=checked_count,
                live_count=live_count,
                offline_count=offline_count,
                snapshots_inserted=snapshots_inserted,
                error_count=error_count,
                error_message="\n".join(errors) if errors else None,
                summary=summary,
            )

    return {
        "status": status,
        **summary,
    }


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Run all collectors.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--config-database", default=DEFAULT_CONFIG_DATABASE)
    args = parser.parse_args()

    summary = collect_all(args.database, args.config_database)
    print(
        "status={status} checked={checked} live={live} offline={offline} "
        "snapshots_inserted={snapshots_inserted} synced_streamers={synced_streamers} errors={error_count} "
        "elapsed_seconds={elapsed_seconds:.2f}".format(
            error_count=len(summary["errors"]),
            **summary,
        )
    )

    for platform, result in summary["results"].items():
        print(
            "{platform}: checked={checked} live={live} offline={offline} "
            "snapshots_inserted={snapshots_inserted} elapsed_seconds={elapsed_seconds:.2f}".format(
                platform=platform,
                **result,
            )
        )

    for error in summary["errors"]:
        print(f"ERROR {error}", file=sys.stderr)

    return 0 if summary["status"] in {"success", "partial_success"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
