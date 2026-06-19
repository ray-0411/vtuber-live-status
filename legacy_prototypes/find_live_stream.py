#!/usr/bin/env python3
"""
Find the currently live YouTube stream for a channel using yt-dlp.

Default channel:
    https://www.youtube.com/@%E6%BE%AARei

Usage:
    python find_live_stream.py
    python find_live_stream.py "https://www.youtube.com/@SomeChannel"
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import yt_dlp


DEFAULT_CHANNEL_URL = "https://www.youtube.com/@%E6%BE%AARei"


class QuietLogger:
    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def iter_entries(info: dict[str, Any]):
    """Yield video entries from a yt-dlp playlist/channel response."""
    entries = info.get("entries") or []
    for entry in entries:
        if entry:
            yield entry


def is_live_entry(entry: dict[str, Any]) -> bool:
    """Return True when yt-dlp marks an entry as currently live."""
    if entry.get("is_live") is True:
        return True

    live_status = entry.get("live_status")
    return live_status == "is_live"


def normalize_video_url(entry: dict[str, Any]) -> str | None:
    url = entry.get("webpage_url") or entry.get("url")
    if not url:
        video_id = entry.get("id")
        if not video_id:
            return None
        return f"https://www.youtube.com/watch?v={video_id}"

    if isinstance(url, str) and url.startswith("http"):
        return url

    return f"https://www.youtube.com/watch?v={url}"


def add_live_stream(
    live_streams: list[dict[str, str]],
    seen_urls: set[str],
    entry: dict[str, Any],
) -> None:
    if not is_live_entry(entry):
        return

    url = normalize_video_url(entry)
    if not url or url in seen_urls:
        return

    seen_urls.add(url)
    live_streams.append(
        {
            "title": entry.get("title") or "(no title)",
            "url": url,
            "concurrent_view_count": str(entry.get("concurrent_view_count") or ""),
        }
    )


def find_live_stream(channel_url: str, deep_scan: bool = False) -> list[dict[str, str]]:
    detail_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "ignoreerrors": True,
        "logger": QuietLogger(),
    }
    flat_opts = {
        **detail_opts,
        "extract_flat": "in_playlist",
        "playlistend": 20,
    }

    channel_url = channel_url.rstrip("/")
    live_streams: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    with yt_dlp.YoutubeDL(detail_opts) as ydl:
        try:
            info = ydl.extract_info(f"{channel_url}/live", download=False)
        except yt_dlp.utils.DownloadError:
            info = None

        if info:
            add_live_stream(live_streams, seen_urls, info)

    if live_streams or not deep_scan:
        return live_streams

    candidate_urls: list[str] = []
    with yt_dlp.YoutubeDL(flat_opts) as ydl:
        for url_to_check in (f"{channel_url}/streams", channel_url):
            try:
                info = ydl.extract_info(url_to_check, download=False)
            except yt_dlp.utils.DownloadError:
                continue

            for entry in iter_entries(info):
                url = normalize_video_url(entry)
                if url and url not in candidate_urls:
                    candidate_urls.append(url)

    with yt_dlp.YoutubeDL(detail_opts) as ydl:
        for candidate_url in candidate_urls[:10]:
            try:
                info = ydl.extract_info(candidate_url, download=False)
            except yt_dlp.utils.DownloadError:
                continue

            if not info:
                continue

            add_live_stream(live_streams, seen_urls, info)

    return live_streams


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(
        description="Find the currently live YouTube stream URL for a channel."
    )
    parser.add_argument(
        "channel_url",
        nargs="?",
        default=DEFAULT_CHANNEL_URL,
        help="YouTube channel URL. Default: %(default)s",
    )
    parser.add_argument(
        "--deep-scan",
        action="store_true",
        help="Also scan recent channel streams if /live does not return a live stream.",
    )
    args = parser.parse_args()

    try:
        live_streams = find_live_stream(args.channel_url, deep_scan=args.deep_scan)
    except yt_dlp.utils.DownloadError as exc:
        print(f"yt-dlp failed: {exc}", file=sys.stderr)
        return 1

    if not live_streams:
        print("No live stream found.")
        return 2

    for stream in live_streams:
        print(stream["title"])
        print(stream["url"])
        if stream["concurrent_view_count"]:
            print(f"Concurrent viewers: {stream['concurrent_view_count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
