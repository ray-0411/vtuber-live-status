#!/usr/bin/env python3
"""
List recent working job records.

Usage:
    python src/list_working.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys


DEFAULT_DATABASE = "live_data.db"


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_where(args: argparse.Namespace) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if args.job:
        clauses.append("job_name = ?")
        params.append(args.job)
    if args.status:
        clauses.append("status = ?")
        params.append(args.status)
    if args.platform:
        clauses.append("platform = ?")
        params.append(args.platform)
    if args.since:
        clauses.append("started_at >= ?")
        params.append(args.since)

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def format_elapsed(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.1f}s"
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="List recent working job records.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--job", choices=["collect_all", "youtube_collector", "twitch_collector"])
    parser.add_argument("--platform", choices=["youtube", "twitch"])
    parser.add_argument("--status", choices=["running", "success", "partial_success", "failed"])
    parser.add_argument("--since", help="Only show rows started at or after this DB time.")
    parser.add_argument("--errors", action="store_true", help="Print error messages under rows.")
    args = parser.parse_args()

    where_sql, params = build_where(args)
    query = f"""
        SELECT
            working_id,
            job_name,
            COALESCE(platform, '-') AS platform,
            status,
            checked_count,
            live_count,
            offline_count,
            snapshots_inserted,
            error_count,
            elapsed_seconds,
            started_at,
            COALESCE(finished_at, '-') AS finished_at,
            error_message
        FROM working
        {where_sql}
        ORDER BY working_id DESC
        LIMIT ?
    """
    params.append(args.limit)

    with sqlite3.connect(args.database) as conn:
        rows = conn.execute(query, params).fetchall()

    print(f"working_rows={len(rows)}")
    print(
        f"{'id':>5} {'job':<18} {'platform':<8} {'status':<15} "
        f"{'chk':>4} {'live':>4} {'off':>4} {'snap':>4} {'err':>3} "
        f"{'elapsed':>8} {'started_at':<19} {'finished_at':<19}"
    )
    for row in rows:
        (
            working_id,
            job_name,
            platform,
            status,
            checked,
            live,
            offline,
            snapshots,
            errors,
            elapsed,
            started_at,
            finished_at,
            error_message,
        ) = row
        print(
            f"{working_id:>5} {job_name:<18} {platform:<8} {status:<15} "
            f"{checked:>4} {live:>4} {offline:>4} {snapshots:>4} {errors:>3} "
            f"{format_elapsed(elapsed):>8} {started_at:<19} {finished_at:<19}"
        )
        if args.errors and error_message:
            for line in str(error_message).splitlines():
                print(f"      error: {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
