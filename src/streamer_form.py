#!/usr/bin/env python3
"""
Small local form for adding or updating streamers.

Usage:
    python src/streamer_form.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from add_streamer import add_streamer
from create_streamer_group import create_streamer_group
from streamer_tables import list_streamer_tables, validate_group_name
from sync_streamers import sync_streamers
from twitch_utils import extract_twitch_login
from youtube_utils import fetch_youtube_channel_id


DEFAULT_CONFIG_DATABASE = "streamer_config.db"
DEFAULT_LIVE_DATABASE = "live_data.db"


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def clean_text(value: str) -> str | None:
    value = value.strip()
    return value or None


def parse_display_order(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    return int(value)


class StreamerForm(ttk.Frame):
    def __init__(self, master: tk.Tk, config_database: str, live_database: str) -> None:
        super().__init__(master, padding=16)
        self.master = master
        self.config_database = config_database
        self.live_database = live_database

        self.group_var = tk.StringVar()
        self.new_group_var = tk.StringVar()
        self.vtuber_id_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.youtube_url_var = tk.StringVar()
        self.youtube_channel_id_var = tk.StringVar()
        self.twitch_url_var = tk.StringVar()
        self.twitch_login_var = tk.StringVar()
        self.display_order_var = tk.StringVar()
        self.note_var = tk.StringVar()
        self.enabled_var = tk.BooleanVar(value=True)
        self.sync_after_save_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready.")

        self.group_combo: ttk.Combobox
        self.fetch_button: ttk.Button
        self.save_button: ttk.Button
        self.duplicate_result_text: tk.Text

        self.grid(sticky="nsew")
        self.build_widgets()
        self.refresh_groups()

    def build_widgets(self) -> None:
        self.master.title("Streamer Form")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(self, text="Group").grid(row=row, column=0, sticky="w", pady=4)
        self.group_combo = ttk.Combobox(self, textvariable=self.group_var, state="readonly")
        self.group_combo.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(self, text="New group").grid(row=row, column=0, sticky="w", pady=4)
        new_group_frame = ttk.Frame(self)
        new_group_frame.grid(row=row, column=1, sticky="ew", pady=4)
        new_group_frame.columnconfigure(0, weight=1)
        ttk.Entry(new_group_frame, textvariable=self.new_group_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(new_group_frame, text="Create", command=self.create_group).grid(
            row=0, column=1, padx=(8, 0)
        )
        row += 1

        ttk.Label(self, text="VTuber ID").grid(row=row, column=0, sticky="w", pady=4)
        vtuber_id_frame = ttk.Frame(self)
        vtuber_id_frame.grid(row=row, column=1, sticky="ew", pady=4)
        vtuber_id_frame.columnconfigure(0, weight=1)
        ttk.Entry(vtuber_id_frame, textvariable=self.vtuber_id_var).grid(
            row=0,
            column=0,
            sticky="ew",
        )
        ttk.Button(vtuber_id_frame, text="Test IDs", command=self.test_duplicate_ids).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )
        row += 1

        row = self.add_entry(row, "Display name", self.name_var)
        row = self.add_entry(row, "YouTube URL", self.youtube_url_var)

        ttk.Label(self, text="YouTube channel ID").grid(row=row, column=0, sticky="w", pady=4)
        channel_frame = ttk.Frame(self)
        channel_frame.grid(row=row, column=1, sticky="ew", pady=4)
        channel_frame.columnconfigure(0, weight=1)
        ttk.Entry(channel_frame, textvariable=self.youtube_channel_id_var).grid(
            row=0, column=0, sticky="ew"
        )
        self.fetch_button = ttk.Button(
            channel_frame,
            text="Auto fetch",
            command=self.fetch_channel_id,
        )
        self.fetch_button.grid(row=0, column=1, padx=(8, 0))
        row += 1

        ttk.Label(self, text="Twitch URL").grid(row=row, column=0, sticky="w", pady=4)
        twitch_url_frame = ttk.Frame(self)
        twitch_url_frame.grid(row=row, column=1, sticky="ew", pady=4)
        twitch_url_frame.columnconfigure(0, weight=1)
        ttk.Entry(twitch_url_frame, textvariable=self.twitch_url_var).grid(
            row=0,
            column=0,
            sticky="ew",
        )
        ttk.Button(twitch_url_frame, text="Fill login", command=self.fill_twitch_login).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )
        self.twitch_url_var.trace_add("write", self.on_twitch_url_changed)
        row += 1

        row = self.add_entry(row, "Twitch login", self.twitch_login_var)
        row = self.add_entry(row, "Display order", self.display_order_var)
        row = self.add_entry(row, "Note", self.note_var)

        options = ttk.Frame(self)
        options.grid(row=row, column=1, sticky="w", pady=(8, 4))
        ttk.Checkbutton(options, text="Enabled", variable=self.enabled_var).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Checkbutton(
            options,
            text="Sync to live_data.db after save",
            variable=self.sync_after_save_var,
        ).grid(row=1, column=0, sticky="w")
        row += 1

        buttons = ttk.Frame(self)
        buttons.grid(row=row, column=1, sticky="e", pady=(12, 4))
        ttk.Button(buttons, text="Clear", command=self.clear_form).grid(row=0, column=0, padx=(0, 8))
        self.save_button = ttk.Button(buttons, text="Save", command=self.save_streamer)
        self.save_button.grid(row=0, column=1)
        row += 1

        ttk.Label(self, textvariable=self.status_var).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(12, 0),
        )
        row += 1

        self.duplicate_result_text = tk.Text(self, height=5, wrap="word")
        self.duplicate_result_text.grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="nsew",
            pady=(8, 0),
        )
        self.duplicate_result_text.configure(state="disabled")
        self.rowconfigure(row, weight=1)

    def add_entry(self, row: int, label: str, variable: tk.StringVar) -> int:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        return row + 1

    def refresh_groups(self) -> None:
        with sqlite3.connect(self.config_database) as conn:
            groups = [table.removeprefix("streamer_") for table in list_streamer_tables(conn)]
        self.group_combo["values"] = groups
        if groups and not self.group_var.get():
            self.group_var.set(groups[0])

    def create_group(self) -> None:
        group_name = self.new_group_var.get().strip()
        if not group_name:
            messagebox.showerror("Missing group", "Enter a group name first.")
            return
        try:
            group_name = validate_group_name(group_name)
            table_name = create_streamer_group(self.config_database, group_name)
        except Exception as exc:
            messagebox.showerror("Create group failed", f"{type(exc).__name__}: {exc}")
            return

        self.refresh_groups()
        self.group_var.set(group_name)
        self.new_group_var.set("")
        self.status_var.set(f"Created {table_name}.")

    def find_duplicate_vtuber_ids(self) -> dict[str, list[str]]:
        locations_by_id: dict[str, list[str]] = {}
        with sqlite3.connect(self.config_database) as conn:
            for table_name in list_streamer_tables(conn):
                rows = conn.execute(
                    f"""
                    SELECT vtuber_id, name
                    FROM {table_name}
                    ORDER BY vtuber_id
                    """
                ).fetchall()
                for vtuber_id, name in rows:
                    locations_by_id.setdefault(vtuber_id, []).append(f"{table_name} / {name}")

        return {
            vtuber_id: locations
            for vtuber_id, locations in locations_by_id.items()
            if len(locations) > 1
        }

    def find_vtuber_id_locations(self, vtuber_id: str) -> list[str]:
        locations: list[str] = []
        with sqlite3.connect(self.config_database) as conn:
            for table_name in list_streamer_tables(conn):
                rows = conn.execute(
                    f"""
                    SELECT name
                    FROM {table_name}
                    WHERE vtuber_id = ?
                    ORDER BY name
                    """,
                    (vtuber_id,),
                ).fetchall()
                locations.extend(f"{table_name} / {name}" for (name,) in rows)
        return locations

    def set_duplicate_result(self, text: str) -> None:
        self.duplicate_result_text.configure(state="normal")
        self.duplicate_result_text.delete("1.0", "end")
        self.duplicate_result_text.insert("1.0", text)
        self.duplicate_result_text.configure(state="disabled")

    def test_duplicate_ids(self) -> None:
        try:
            current_vtuber_id = self.vtuber_id_var.get().strip()
            current_locations = (
                self.find_vtuber_id_locations(current_vtuber_id)
                if current_vtuber_id
                else []
            )
            duplicates = self.find_duplicate_vtuber_ids()
        except Exception as exc:
            messagebox.showerror("Test failed", f"{type(exc).__name__}: {exc}")
            return

        if not current_locations and not duplicates:
            self.status_var.set("No duplicate VTuber IDs found.")
            if current_vtuber_id:
                self.set_duplicate_result(f"{current_vtuber_id} is not used yet.")
            else:
                self.set_duplicate_result("No duplicate VTuber IDs found.")
            return

        lines: list[str] = []
        if current_vtuber_id:
            if current_locations:
                lines.append(f"Current ID is already used: {current_vtuber_id}")
                lines.extend(f"- {location}" for location in current_locations)
            else:
                lines.append(f"Current ID is not used yet: {current_vtuber_id}")

        if duplicates:
            if lines:
                lines.append("")
            lines.append("Duplicate VTuber IDs found across streamer tables:")
            for vtuber_id, locations in sorted(duplicates.items()):
                lines.append(f"- {vtuber_id}")
                lines.extend(f"  - {location}" for location in locations)
        result = "\n".join(lines)
        if current_locations:
            self.status_var.set(f"{current_vtuber_id} is already used.")
        else:
            self.status_var.set(f"Found {len(duplicates)} duplicate VTuber ID(s).")
        self.set_duplicate_result(result)

    def fetch_channel_id(self) -> None:
        youtube_url = self.youtube_url_var.get().strip()
        if not youtube_url:
            messagebox.showerror("Missing YouTube URL", "Enter a YouTube URL first.")
            return

        self.fetch_button.configure(state="disabled")
        self.status_var.set("Fetching YouTube channel ID...")

        def worker() -> None:
            try:
                channel_id = fetch_youtube_channel_id(youtube_url)
            except Exception as exc:
                self.after(0, self.finish_fetch_channel_id, None, exc)
                return
            self.after(0, self.finish_fetch_channel_id, channel_id, None)

        threading.Thread(target=worker, daemon=True).start()

    def finish_fetch_channel_id(self, channel_id: str | None, exc: Exception | None) -> None:
        self.fetch_button.configure(state="normal")
        if exc is not None:
            self.status_var.set("Failed to fetch YouTube channel ID.")
            messagebox.showerror("Fetch failed", f"{type(exc).__name__}: {exc}")
            return
        if not channel_id:
            self.status_var.set("No YouTube channel ID found.")
            messagebox.showwarning("Not found", "No YouTube channel ID was found.")
            return

        self.youtube_channel_id_var.set(channel_id)
        self.status_var.set(f"Fetched YouTube channel ID: {channel_id}")

    def on_twitch_url_changed(self, *_args: object) -> None:
        if self.twitch_login_var.get().strip():
            return
        login = extract_twitch_login(self.twitch_url_var.get())
        if login:
            self.twitch_login_var.set(login)

    def fill_twitch_login(self) -> None:
        login = extract_twitch_login(self.twitch_url_var.get())
        if not login:
            messagebox.showwarning("Not found", "No Twitch login was found in the URL.")
            return
        self.twitch_login_var.set(login)
        self.status_var.set(f"Filled Twitch login: {login}")

    def save_streamer(self) -> None:
        try:
            group_name = validate_group_name(self.group_var.get())
            vtuber_id = self.vtuber_id_var.get().strip()
            name = self.name_var.get().strip()
            if not vtuber_id:
                raise ValueError("VTuber ID is required.")
            if not name:
                raise ValueError("Display name is required.")

            table_name = add_streamer(
                database=self.config_database,
                group_name=group_name,
                vtuber_id=vtuber_id,
                name=name,
                youtube_url=clean_text(self.youtube_url_var.get()),
                youtube_channel_id=clean_text(self.youtube_channel_id_var.get()),
                twitch_url=clean_text(self.twitch_url_var.get()),
                twitch_login=clean_text(self.twitch_login_var.get()),
                enabled=1 if self.enabled_var.get() else 0,
                display_order=parse_display_order(self.display_order_var.get()),
                note=clean_text(self.note_var.get()),
            )
            synced_text = ""
            if self.sync_after_save_var.get():
                synced_count = sync_streamers(self.config_database, self.live_database)
                synced_text = f" Synced {synced_count} streamers."
        except Exception as exc:
            messagebox.showerror("Save failed", f"{type(exc).__name__}: {exc}")
            return

        self.status_var.set(f"Saved {vtuber_id} in {table_name}.{synced_text}")
        messagebox.showinfo("Saved", f"Saved {vtuber_id} in {table_name}.{synced_text}")

    def clear_form(self) -> None:
        self.vtuber_id_var.set("")
        self.name_var.set("")
        self.youtube_url_var.set("")
        self.youtube_channel_id_var.set("")
        self.twitch_url_var.set("")
        self.twitch_login_var.set("")
        self.display_order_var.set("")
        self.note_var.set("")
        self.enabled_var.set(True)
        self.status_var.set("Ready.")


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Open the streamer add/update form.")
    parser.add_argument("--config-database", default=DEFAULT_CONFIG_DATABASE)
    parser.add_argument("--live-database", default=DEFAULT_LIVE_DATABASE)
    args = parser.parse_args()

    root = tk.Tk()
    root.minsize(640, 520)
    StreamerForm(root, args.config_database, args.live_database)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
