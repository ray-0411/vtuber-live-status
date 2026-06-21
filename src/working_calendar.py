#!/usr/bin/env python3
"""
Show working job history in a simple calendar window.

Usage:
    python src/working_calendar.py
"""

from __future__ import annotations

import argparse
import calendar
import sqlite3
import sys
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from tkinter import ttk


DEFAULT_DATABASE = "live_data.db"
APP_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
EXPECTED_INTERVAL_MINUTES = 5
MISSING_GAP_MINUTES = 10


STATUS_COLORS = {
    "success": "#a1ffa1",
    "missing": "#fff696",
    "problem": "#ff9797",
    "running": "#64b5f6",
    "empty": "#e0e0e0",
    "future": "#f5f5f5",
}


@dataclass(frozen=True)
class DaySummary:
    day: date
    status: str
    collect_count: int
    failed_count: int
    partial_count: int
    error_count: int
    running_count: int
    success_count: int
    first_started_at: str | None
    last_started_at: str | None
    max_gap_minutes: float | None
    expected_count: int
    completion_rate: float
    youtube_checked: int = 0
    youtube_live: int = 0
    youtube_offline: int = 0
    youtube_errors: int = 0
    twitch_checked: int = 0
    twitch_live: int = 0
    twitch_offline: int = 0
    twitch_errors: int = 0


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def parse_db_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, APP_TIME_FORMAT)
    except ValueError:
        return None


def day_range(day: date) -> tuple[str, str]:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    return start.strftime(APP_TIME_FORMAT), end.strftime(APP_TIME_FORMAT)


def read_collect_rows(conn: sqlite3.Connection, day: date) -> list[sqlite3.Row]:
    start, end = day_range(day)
    return conn.execute(
        """
        SELECT
            working_id,
            job_name,
            platform,
            status,
            started_at,
            finished_at,
            elapsed_seconds,
            checked_count,
            live_count,
            offline_count,
            snapshots_inserted,
            error_count,
            error_message
        FROM working
        WHERE job_name = 'collect_all'
          AND started_at >= ?
          AND started_at < ?
        ORDER BY started_at
        """,
        (start, end),
    ).fetchall()


def read_job_rows(conn: sqlite3.Connection, day: date) -> list[sqlite3.Row]:
    start, end = day_range(day)
    return conn.execute(
        """
        SELECT
            working_id,
            job_name,
            platform,
            status,
            started_at,
            finished_at,
            elapsed_seconds,
            checked_count,
            live_count,
            offline_count,
            snapshots_inserted,
            error_count,
            error_message
        FROM working
        WHERE job_name IN ('collect_all', 'youtube_collector', 'twitch_collector')
          AND started_at >= ?
          AND started_at < ?
        ORDER BY started_at, working_id
        """,
        (start, end),
    ).fetchall()


def platform_totals(rows: list[sqlite3.Row], job_name: str) -> tuple[int, int, int, int]:
    matched = [row for row in rows if row["job_name"] == job_name]
    return (
        sum(int(row["checked_count"] or 0) for row in matched),
        sum(int(row["live_count"] or 0) for row in matched),
        sum(int(row["offline_count"] or 0) for row in matched),
        sum(int(row["error_count"] or 0) for row in matched),
    )


def read_platform_rows_for_slot(conn: sqlite3.Connection, collect_row: sqlite3.Row) -> list[sqlite3.Row]:
    started = parse_db_time(str(collect_row["started_at"]))
    if started is None:
        return []

    end = started + timedelta(minutes=EXPECTED_INTERVAL_MINUTES)
    return conn.execute(
        """
        SELECT
            working_id,
            job_name,
            platform,
            status,
            started_at,
            finished_at,
            elapsed_seconds,
            checked_count,
            live_count,
            offline_count,
            snapshots_inserted,
            error_count,
            error_message
        FROM working
        WHERE job_name IN ('youtube_collector', 'twitch_collector')
          AND started_at >= ?
          AND started_at < ?
        ORDER BY job_name, started_at, working_id
        """,
        (started.strftime(APP_TIME_FORMAT), end.strftime(APP_TIME_FORMAT)),
    ).fetchall()


def expected_slot_count(day: date, now: datetime) -> int:
    if day > now.date():
        return 0
    if day < now.date():
        return 24 * 60 // EXPECTED_INTERVAL_MINUTES
    elapsed_minutes = now.hour * 60 + now.minute
    return elapsed_minutes // EXPECTED_INTERVAL_MINUTES + 1


def row_slot(row: sqlite3.Row) -> tuple[int, int] | None:
    started = parse_db_time(str(row["started_at"]))
    if started is None:
        return None
    minute_slot = (started.minute // EXPECTED_INTERVAL_MINUTES) * EXPECTED_INTERVAL_MINUTES
    return started.hour, minute_slot


def slot_status(row: sqlite3.Row | None) -> str:
    if row is None:
        return "empty"
    if row["status"] == "success" and int(row["error_count"] or 0) == 0:
        return "success"
    if row["status"] == "running":
        return "running"
    return "problem"


def status_score(status: str) -> float:
    if status == "success":
        return 1.0
    if status == "running":
        return 0.5
    return 0.0


def blend_color(low: tuple[int, int, int], high: tuple[int, int, int], ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    red = round(low[0] + (high[0] - low[0]) * ratio)
    green = round(low[1] + (high[1] - low[1]) * ratio)
    blue = round(low[2] + (high[2] - low[2]) * ratio)
    return f"#{red:02x}{green:02x}{blue:02x}"


def completion_color(summary: DaySummary, in_month: bool) -> str:
    if not in_month:
        return "#eeeeee"
    if summary.expected_count == 0:
        return STATUS_COLORS["future"]
    if summary.collect_count == 0:
        return STATUS_COLORS["empty"]
    if summary.collect_count < summary.expected_count:
        # Blend yellow into the completion color when there are missing slots.
        missing_ratio = 1 - (summary.collect_count / max(summary.expected_count, 1))
        base = blend_color((255, 151, 151), (161, 255, 161), summary.completion_rate)
        if missing_ratio > 0.15:
            return STATUS_COLORS["missing"]
        return base
    return blend_color((255, 151, 151), (161, 255, 161), summary.completion_rate)


def summarize_day(conn: sqlite3.Connection, day: date, now: datetime) -> DaySummary:
    rows = read_collect_rows(conn, day)
    job_rows = read_job_rows(conn, day)
    youtube_checked, youtube_live, youtube_offline, youtube_errors = platform_totals(
        job_rows,
        "youtube_collector",
    )
    twitch_checked, twitch_live, twitch_offline, twitch_errors = platform_totals(
        job_rows,
        "twitch_collector",
    )
    if not rows:
        status = "future" if day > now.date() else "empty"
        expected_count = expected_slot_count(day, now)
        return DaySummary(
            day=day,
            status=status,
            collect_count=0,
            failed_count=0,
            partial_count=0,
            error_count=0,
            running_count=0,
            success_count=0,
            first_started_at=None,
            last_started_at=None,
            max_gap_minutes=None,
            expected_count=expected_count,
            completion_rate=0.0,
            youtube_checked=youtube_checked,
            youtube_live=youtube_live,
            youtube_offline=youtube_offline,
            youtube_errors=youtube_errors,
            twitch_checked=twitch_checked,
            twitch_live=twitch_live,
            twitch_offline=twitch_offline,
            twitch_errors=twitch_errors,
        )

    failed_count = sum(1 for row in rows if row["status"] == "failed")
    partial_count = sum(1 for row in rows if row["status"] == "partial_success")
    error_count = sum(int(row["error_count"] or 0) for row in rows)
    running_count = sum(1 for row in rows if row["status"] == "running")
    success_count = sum(
        1
        for row in rows
        if row["status"] == "success" and int(row["error_count"] or 0) == 0
    )
    expected_count = expected_slot_count(day, now)
    completion_rate = sum(status_score(slot_status(row)) for row in rows) / max(
        expected_count,
        len(rows),
        1,
    )

    started_times = [
        parsed
        for parsed in (parse_db_time(str(row["started_at"])) for row in rows)
        if parsed is not None
    ]
    max_gap_minutes: float | None = None
    if len(started_times) >= 2:
        gaps = [
            (right - left).total_seconds() / 60
            for left, right in zip(started_times, started_times[1:])
        ]
        max_gap_minutes = max(gaps)

    status = "normal"
    if failed_count or partial_count or error_count:
        status = "problem"
    elif running_count:
        latest_running = max(
            (
                parse_db_time(str(row["started_at"]))
                for row in rows
                if row["status"] == "running"
            ),
            default=None,
        )
        if latest_running is None or now - latest_running > timedelta(minutes=MISSING_GAP_MINUTES):
            status = "missing"
    elif max_gap_minutes is not None and max_gap_minutes > MISSING_GAP_MINUTES:
        status = "missing"
    elif day == now.date() and started_times:
        last_started = max(started_times)
        if now - last_started > timedelta(minutes=MISSING_GAP_MINUTES):
            status = "missing"

    return DaySummary(
        day=day,
        status=status,
        collect_count=len(rows),
        failed_count=failed_count,
        partial_count=partial_count,
        error_count=error_count,
        running_count=running_count,
        success_count=success_count,
        first_started_at=str(rows[0]["started_at"]),
        last_started_at=str(rows[-1]["started_at"]),
        max_gap_minutes=max_gap_minutes,
        expected_count=expected_count,
        completion_rate=completion_rate,
        youtube_checked=youtube_checked,
        youtube_live=youtube_live,
        youtube_offline=youtube_offline,
        youtube_errors=youtube_errors,
        twitch_checked=twitch_checked,
        twitch_live=twitch_live,
        twitch_offline=twitch_offline,
        twitch_errors=twitch_errors,
    )


class WorkingCalendar(ttk.Frame):
    def __init__(self, master: tk.Tk, database: str) -> None:
        super().__init__(master, padding=12)
        self.master = master
        self.database = database
        today = date.today()
        self.year = today.year
        self.month = today.month
        self.day_buttons: list[tk.Button] = []
        self.slot_buttons: dict[tuple[int, int], tk.Button] = {}
        self.slot_rows: dict[tuple[int, int], sqlite3.Row] = {}

        self.month_label_var = tk.StringVar()
        self.summary_var = tk.StringVar()

        self.grid(sticky="nsew")
        self.build_widgets()
        self.render_month()

    def build_widgets(self) -> None:
        self.master.title("Working Calendar")
        self.master.geometry("1240x760")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Button(top, text="< Prev", command=self.previous_month).pack(side="left")
        ttk.Label(top, textvariable=self.month_label_var, font=("Segoe UI", 14, "bold")).pack(
            side="left",
            padx=16,
        )
        ttk.Button(top, text="Next >", command=self.next_month).pack(side="left")
        ttk.Button(top, text="Today", command=self.go_today).pack(side="left", padx=(12, 0))

        legend = ttk.Frame(top)
        legend.pack(side="right")
        for label, key in [
            ("Success", "success"),
            ("Missing", "missing"),
            ("Problem", "problem"),
            ("Running", "running"),
            ("No data", "empty"),
        ]:
            swatch = tk.Label(legend, text="  ", bg=STATUS_COLORS[key])
            swatch.pack(side="left", padx=(8, 3))
            ttk.Label(legend, text=label).pack(side="left")

        calendar_frame = ttk.Frame(self)
        calendar_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        for col in range(7):
            calendar_frame.columnconfigure(col, weight=1)
        for row in range(7):
            calendar_frame.rowconfigure(row, weight=1)

        for col, label in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            ttk.Label(calendar_frame, text=label, anchor="center").grid(
                row=0,
                column=col,
                sticky="ew",
                padx=2,
                pady=2,
            )

        for index in range(42):
            button = tk.Button(
                calendar_frame,
                text="",
                relief="ridge",
                anchor="nw",
                justify="left",
                padx=8,
                pady=6,
            )
            button.grid(row=index // 7 + 1, column=index % 7, sticky="nsew", padx=2, pady=2)
            self.day_buttons.append(button)

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(1, weight=0)
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)
        ttk.Label(right, textvariable=self.summary_var, justify="left").grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )

        self.grid_frame = ttk.Frame(right)
        self.grid_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.build_slot_grid()

        self.detail_text = tk.Text(right, wrap="word", height=20)
        self.detail_text.grid(row=2, column=0, sticky="nsew")
        self.detail_text.configure(state="disabled")

    def build_slot_grid(self) -> None:
        ttk.Label(self.grid_frame, text="min\\hr", anchor="center").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=1,
            pady=1,
        )
        for hour in range(24):
            ttk.Label(self.grid_frame, text=f"{hour:02d}", anchor="center").grid(
                row=0,
                column=hour + 1,
                sticky="ew",
                padx=1,
                pady=1,
            )
            self.grid_frame.columnconfigure(hour + 1, weight=1)

        for row_index, minute in enumerate(range(0, 60, EXPECTED_INTERVAL_MINUTES), start=1):
            ttk.Label(self.grid_frame, text=f"{minute:02d}", anchor="center").grid(
                row=row_index,
                column=0,
                sticky="ew",
                padx=1,
                pady=1,
            )
            for hour in range(24):
                button = tk.Button(
                    self.grid_frame,
                    text="",
                    width=2,
                    height=1,
                    relief="ridge",
                    padx=0,
                    pady=0,
                    command=lambda h=hour, m=minute: self.show_slot_detail(h, m),
                )
                button.grid(row=row_index, column=hour + 1, sticky="nsew", padx=1, pady=1)
                self.slot_buttons[(hour, minute)] = button

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        return conn

    def render_month(self) -> None:
        self.month_label_var.set(f"{self.year}-{self.month:02d}")
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self.year, self.month)
        days = [day for week in weeks for day in week]
        while len(days) < 42:
            days.append(days[-1] + timedelta(days=1))

        now = datetime.now()
        with self.connect() as conn:
            summaries = {day: summarize_day(conn, day, now) for day in days}

        for button, day in zip(self.day_buttons, days):
            summary = summaries[day]
            in_month = day.month == self.month
            color = completion_color(summary, in_month)
            button.configure(
                bg=color,
                activebackground=color,
                fg="#000000",
                text=self.button_text(summary),
                command=lambda selected=day: self.show_day(selected),
            )

        self.show_day(date.today() if date.today().month == self.month else date(self.year, self.month, 1))

    def button_text(self, summary: DaySummary) -> str:
        if summary.collect_count == 0:
            return f"{summary.day.day}\nno data"
        percent = round(summary.completion_rate * 100)
        return (
            f"{summary.day.day}\n"
            f"{percent}%\n"
            f"{summary.success_count}/{summary.expected_count}\n"
            f"err {summary.error_count}"
        )

    def show_day(self, day: date) -> None:
        with self.connect() as conn:
            summary = summarize_day(conn, day, datetime.now())
            rows = read_collect_rows(conn, day)

        max_gap = "-" if summary.max_gap_minutes is None else f"{summary.max_gap_minutes:.1f} min"
        problem_runs = (
            f"failed {summary.failed_count}, "
            f"partial {summary.partial_count}, "
            f"collect_all errors {summary.error_count}"
        )
        self.summary_var.set(
            "\n".join(
                [
                    f"Date: {day.isoformat()}",
                    f"Status: {summary.status}",
                    f"Completion: {summary.completion_rate:.0%}",
                    f"collect_all: ran {summary.collect_count} / expected {summary.expected_count}",
                    f"collect_all success: {summary.success_count}",
                    f"Problem runs: {problem_runs}",
                    f"Running runs: {summary.running_count}",
                    (
                        "YouTube: "
                        f"checked {summary.youtube_checked}, "
                        f"live {summary.youtube_live}, "
                        f"offline {summary.youtube_offline}, "
                        f"errors {summary.youtube_errors}"
                    ),
                    (
                        "Twitch: "
                        f"checked {summary.twitch_checked}, "
                        f"live {summary.twitch_live}, "
                        f"offline {summary.twitch_offline}, "
                        f"errors {summary.twitch_errors}"
                    ),
                    f"First run: {summary.first_started_at or '-'}",
                    f"Last run: {summary.last_started_at or '-'}",
                    f"Max gap: {max_gap}",
                ]
            )
        )

        self.render_slot_grid(rows, day)
        self.set_detail_text("Click a 5-minute cell to view details.")

    def render_slot_grid(self, rows: list[sqlite3.Row], selected_day: date) -> None:
        self.slot_rows = {}
        now = datetime.now()
        expected_until = expected_slot_count(selected_day, now)
        slots_elapsed = 0

        for row in rows:
            slot = row_slot(row)
            if slot is not None:
                self.slot_rows[slot] = row

        for minute in range(0, 60, EXPECTED_INTERVAL_MINUTES):
            for hour in range(24):
                button = self.slot_buttons[(hour, minute)]
                slot_index = (hour * 60 + minute) // EXPECTED_INTERVAL_MINUTES + 1
                row = self.slot_rows.get((hour, minute))
                status = slot_status(row)
                if row is None:
                    if selected_day > now.date() or slot_index > expected_until:
                        color = STATUS_COLORS["future"]
                    else:
                        color = STATUS_COLORS["missing"]
                else:
                    color = STATUS_COLORS[status]
                button.configure(
                    bg=color,
                    activebackground=color,
                    text="",
                    state="normal",
                )
                slots_elapsed += 1

    def show_slot_detail(self, hour: int, minute: int) -> None:
        row = self.slot_rows.get((hour, minute))
        if row is None:
            self.set_detail_text(f"No collect_all row for {hour:02d}:{minute:02d}.")
            return

        with self.connect() as conn:
            platform_rows = read_platform_rows_for_slot(conn, row)

        lines: list[str] = []
        elapsed = "-" if row["elapsed_seconds"] is None else f"{float(row['elapsed_seconds']):.1f}s"
        lines.append(f"Slot: {hour:02d}:{minute:02d}")
        lines.append("")
        lines.append("COLLECT_ALL")
        lines.append(f"working_id: {row['working_id']}")
        lines.append(f"status: {row['status']}")
        lines.append(f"started_at: {row['started_at']}")
        lines.append(f"finished_at: {row['finished_at'] or '-'}")
        lines.append(f"elapsed: {elapsed}")
        lines.append(f"checked: {row['checked_count']}")
        lines.append(f"live: {row['live_count']}")
        lines.append(f"offline: {row['offline_count']}")
        lines.append(f"snapshots_inserted: {row['snapshots_inserted']}")
        lines.append(f"errors: {row['error_count']}")

        for platform_row in platform_rows:
            platform_name = "YouTube" if platform_row["job_name"] == "youtube_collector" else "Twitch"
            platform_elapsed = (
                "-"
                if platform_row["elapsed_seconds"] is None
                else f"{float(platform_row['elapsed_seconds']):.1f}s"
            )
            lines.append("")
            lines.append(platform_name.upper())
            lines.append(f"working_id: {platform_row['working_id']}")
            lines.append(f"status: {platform_row['status']}")
            lines.append(f"started_at: {platform_row['started_at']}")
            lines.append(f"finished_at: {platform_row['finished_at'] or '-'}")
            lines.append(f"elapsed: {platform_elapsed}")
            lines.append(f"checked: {platform_row['checked_count']}")
            lines.append(f"live: {platform_row['live_count']}")
            lines.append(f"offline: {platform_row['offline_count']}")
            lines.append(f"snapshots_inserted: {platform_row['snapshots_inserted']}")
            lines.append(f"errors: {platform_row['error_count']}")

        if row["error_message"]:
            lines.append("")
            lines.append("COLLECT_ALL ERRORS:")
            for message in str(row["error_message"]).splitlines():
                lines.append(f"- {message}")

        for platform_row in platform_rows:
            if not platform_row["error_message"]:
                continue
            platform_name = "YOUTUBE" if platform_row["job_name"] == "youtube_collector" else "TWITCH"
            lines.append("")
            lines.append(f"{platform_name} ERRORS:")
            for message in str(platform_row["error_message"]).splitlines():
                lines.append(f"- {message}")
        self.set_detail_text("\n".join(lines))

    def set_detail_text(self, text: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def previous_month(self) -> None:
        if self.month == 1:
            self.year -= 1
            self.month = 12
        else:
            self.month -= 1
        self.render_month()

    def next_month(self) -> None:
        if self.month == 12:
            self.year += 1
            self.month = 1
        else:
            self.month += 1
        self.render_month()

    def go_today(self) -> None:
        today = date.today()
        self.year = today.year
        self.month = today.month
        self.render_month()


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Show working job history calendar.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    args = parser.parse_args()

    root = tk.Tk()
    WorkingCalendar(root, args.database)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
