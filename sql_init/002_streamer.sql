CREATE TABLE IF NOT EXISTS streamer (
    vtuber_id TEXT PRIMARY KEY,
    group_name TEXT NOT NULL,
    name TEXT NOT NULL,
    youtube_url TEXT,
    youtube_channel_id TEXT,
    twitch_url TEXT,
    twitch_login TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER,
    note TEXT,
    synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
