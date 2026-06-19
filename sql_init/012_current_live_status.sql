CREATE TABLE IF NOT EXISTS current_live_status (
    vtuber_id TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'twitch')),
    is_live INTEGER NOT NULL DEFAULT 0,
    stream_id INTEGER,
    viewer_count INTEGER,
    stream_url TEXT,
    title TEXT,
    category TEXT,
    tags TEXT,
    started_at TEXT,
    last_checked_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    last_live_at TEXT,
    PRIMARY KEY (vtuber_id, platform),
    FOREIGN KEY (stream_id) REFERENCES stream(stream_id)
);
