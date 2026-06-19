-- Template for streamer group tables.
-- Do not execute this file directly unless GROUP_NAME is replaced first.
--
-- Table naming rule:
--   streamer_<group_name>
--
-- Example:
--   streamer_meridian

CREATE TABLE IF NOT EXISTS streamer_GROUP_NAME (
    vtuber_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    youtube_url TEXT,
    youtube_channel_id TEXT,
    twitch_url TEXT,
    twitch_login TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours'))
);
