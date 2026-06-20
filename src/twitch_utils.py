from __future__ import annotations

import re
import urllib.parse


TWITCH_LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9_]{4,25}$")


def extract_twitch_login(twitch_url: str | None) -> str | None:
    if not twitch_url:
        return None

    value = twitch_url.strip()
    if not value:
        return None

    if "://" not in value:
        value = f"https://{value}"

    parsed = urllib.parse.urlparse(value)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host.removeprefix("www.")
    if host not in {"twitch.tv", "m.twitch.tv"}:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None

    login = parts[0].lower()
    if login in {"directory", "downloads", "jobs", "p", "settings", "subscriptions"}:
        return None
    if not TWITCH_LOGIN_PATTERN.fullmatch(login):
        return None
    return login
