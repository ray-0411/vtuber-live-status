from __future__ import annotations

import json
import sqlite3
from typing import Any


def start_job(conn: sqlite3.Connection, job_name: str, platform: str | None = None) -> int:
    cursor = conn.execute(
        """
        INSERT INTO working (
            job_name,
            platform,
            status
        )
        VALUES (?, ?, 'running')
        """,
        (job_name, platform),
    )
    return int(cursor.lastrowid)


def finish_job(
    conn: sqlite3.Connection,
    working_id: int,
    *,
    status: str,
    elapsed_seconds: float,
    checked_count: int = 0,
    live_count: int = 0,
    offline_count: int = 0,
    snapshots_inserted: int = 0,
    error_count: int = 0,
    error_message: str | None = None,
    summary: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        UPDATE working
        SET
            status = ?,
            finished_at = CURRENT_TIMESTAMP,
            elapsed_seconds = ?,
            checked_count = ?,
            live_count = ?,
            offline_count = ?,
            snapshots_inserted = ?,
            error_count = ?,
            error_message = ?,
            summary = ?
        WHERE working_id = ?
        """,
        (
            status,
            elapsed_seconds,
            checked_count,
            live_count,
            offline_count,
            snapshots_inserted,
            error_count,
            error_message,
            json.dumps(summary, ensure_ascii=False) if summary is not None else None,
            working_id,
        ),
    )


def fail_job(
    conn: sqlite3.Connection,
    working_id: int,
    *,
    elapsed_seconds: float,
    error_message: str,
    summary: dict[str, Any] | None = None,
) -> None:
    finish_job(
        conn,
        working_id,
        status="failed",
        elapsed_seconds=elapsed_seconds,
        error_count=1,
        error_message=error_message,
        summary=summary,
    )
