from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass


GROUP_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
STREAMER_TABLE_PATTERN = re.compile(r"^streamer_[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Streamer:
    group_name: str
    table_name: str
    vtuber_id: str
    name: str
    youtube_url: str | None
    youtube_channel_id: str | None
    twitch_url: str | None
    twitch_login: str | None
    enabled: int
    display_order: int | None
    note: str | None


def validate_group_name(group_name: str) -> str:
    group_name = group_name.strip().lower()
    if not GROUP_NAME_PATTERN.fullmatch(group_name):
        raise ValueError(
            "Group name must start with a lowercase letter and contain only "
            "lowercase letters, numbers, and underscores."
        )
    return group_name


def table_name_for_group(group_name: str) -> str:
    return f"streamer_{validate_group_name(group_name)}"


def validate_streamer_table_name(table_name: str) -> str:
    if not STREAMER_TABLE_PATTERN.fullmatch(table_name):
        raise ValueError(f"Invalid streamer table name: {table_name}")
    return table_name


def list_streamer_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name LIKE 'streamer_%'
        ORDER BY name
        """
    ).fetchall()

    return [
        validate_streamer_table_name(row[0])
        for row in rows
        if row[0] != "streamer_GROUP_NAME"
    ]


def read_streamers(conn: sqlite3.Connection, enabled_only: bool = True) -> list[Streamer]:
    streamers: list[Streamer] = []
    for table_name in list_streamer_tables(conn):
        where = "WHERE enabled = 1" if enabled_only else ""
        rows = conn.execute(
            f"""
            SELECT
                vtuber_id,
                name,
                youtube_url,
                youtube_channel_id,
                twitch_url,
                twitch_login,
                enabled,
                display_order,
                note
            FROM {table_name}
            {where}
            ORDER BY COALESCE(display_order, 999999), vtuber_id
            """
        ).fetchall()

        group_name = table_name.removeprefix("streamer_")
        for row in rows:
            streamers.append(
                Streamer(
                    group_name=group_name,
                    table_name=table_name,
                    vtuber_id=row[0],
                    name=row[1],
                    youtube_url=row[2],
                    youtube_channel_id=row[3],
                    twitch_url=row[4],
                    twitch_login=row[5],
                    enabled=row[6],
                    display_order=row[7],
                    note=row[8],
                )
            )

    return streamers


def read_live_streamers(conn: sqlite3.Connection, enabled_only: bool = True) -> list[Streamer]:
    where = "WHERE enabled = 1" if enabled_only else ""
    rows = conn.execute(
        f"""
        SELECT
            group_name,
            vtuber_id,
            name,
            youtube_url,
            youtube_channel_id,
            twitch_url,
            twitch_login,
            enabled,
            display_order,
            note
        FROM streamer
        {where}
        ORDER BY group_name, COALESCE(display_order, 999999), vtuber_id
        """
    ).fetchall()

    return [
        Streamer(
            group_name=row[0],
            table_name="streamer",
            vtuber_id=row[1],
            name=row[2],
            youtube_url=row[3],
            youtube_channel_id=row[4],
            twitch_url=row[5],
            twitch_login=row[6],
            enabled=row[7],
            display_order=row[8],
            note=row[9],
        )
        for row in rows
    ]
