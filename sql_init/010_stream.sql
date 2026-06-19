CREATE TABLE IF NOT EXISTS stream (
    stream_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vtuber_id TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'twitch')),
    platform_stream_id TEXT NOT NULL,
    stream_url TEXT,
    title TEXT,
    category TEXT,
    tags TEXT,
    started_at TEXT,
    ended_at TEXT,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    UNIQUE (platform, platform_stream_id)
);
