CREATE TABLE IF NOT EXISTS stream_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_id INTEGER NOT NULL,
    vtuber_id TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'twitch')),
    viewer_count INTEGER NOT NULL,
    captured_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    title TEXT,
    category TEXT,
    tags TEXT,
    FOREIGN KEY (stream_id) REFERENCES stream(stream_id)
);
