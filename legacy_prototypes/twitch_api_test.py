#!/usr/bin/env python3
"""
Small Twitch Helix API test.

Credentials are read from environment variables:
    TWITCH_CLIENT_ID
    TWITCH_CLIENT_SECRET

Usage:
    python twitch_api_test.py kspksp reirei_neon
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Any


TOKEN_URL = "https://id.twitch.tv/oauth2/token"
STREAMS_URL = "https://api.twitch.tv/helix/streams"


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers or {},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
        return json.loads(body), dict(response.headers)


def get_app_access_token(client_id: str, client_secret: str) -> str:
    payload = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")

    data, _headers = request_json(
        TOKEN_URL,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
    )
    return data["access_token"]


def get_streams(client_id: str, access_token: str, logins: list[str]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    params = [("user_login", login) for login in logins]
    query = urllib.parse.urlencode(params)
    url = f"{STREAMS_URL}?{query}"
    data, headers = request_json(
        url,
        headers={
            "Client-Id": client_id,
            "Authorization": f"Bearer {access_token}",
        },
    )
    return data.get("data", []), headers


def main() -> int:
    configure_output_encoding()

    parser = argparse.ArgumentParser(description="Test Twitch Get Streams API.")
    parser.add_argument(
        "logins",
        nargs="*",
        default=["kspksp", "reirei_neon", "koyuki_teraz"],
        help="Twitch login names to check.",
    )
    args = parser.parse_args()

    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET.", file=sys.stderr)
        return 1

    started = time.perf_counter()
    token = get_app_access_token(client_id, client_secret)
    streams, headers = get_streams(client_id, token, args.logins)
    elapsed = time.perf_counter() - started

    live_by_login = {stream["user_login"].lower(): stream for stream in streams}
    print(f"checked={len(args.logins)} live={len(streams)} elapsed_seconds={elapsed:.2f}")
    print(
        "rate_limit="
        f"{headers.get('Ratelimit-Remaining', '?')}/"
        f"{headers.get('Ratelimit-Limit', '?')}"
    )

    for login in args.logins:
        stream = live_by_login.get(login.lower())
        if not stream:
            print(f"--   {login}: no live")
            continue

        print(
            f"LIVE {login}: {stream.get('viewer_count')} viewers | "
            f"{stream.get('user_name')} | {stream.get('title')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
