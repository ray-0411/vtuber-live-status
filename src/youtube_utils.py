from __future__ import annotations

import re
from typing import Any

import yt_dlp


YOUTUBE_CHANNEL_ID_PATTERN = re.compile(r"(?:youtube\.com/channel/|^)(UC[A-Za-z0-9_-]{22})")


def extract_channel_id_from_text(value: str | None) -> str | None:
    if not value:
        return None
    match = YOUTUBE_CHANNEL_ID_PATTERN.search(value)
    if match:
        return match.group(1)
    return None


def find_channel_id(info: dict[str, Any] | None) -> str | None:
    if not info:
        return None

    for key in ("channel_id", "uploader_id"):
        channel_id = extract_channel_id_from_text(info.get(key))
        if channel_id:
            return channel_id

    channel_url_id = extract_channel_id_from_text(info.get("channel_url"))
    if channel_url_id:
        return channel_url_id

    entries = info.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                channel_id = find_channel_id(entry)
                if channel_id:
                    return channel_id

    return None


def fetch_youtube_channel_id(youtube_url: str) -> str | None:
    direct_id = extract_channel_id_from_text(youtube_url)
    if direct_id:
        return direct_id

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": 1,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
    return find_channel_id(info)


def build_youtube_channel_url(youtube_url: str | None, youtube_channel_id: str | None) -> str | None:
    if youtube_channel_id:
        return f"https://www.youtube.com/channel/{youtube_channel_id}"
    return youtube_url
