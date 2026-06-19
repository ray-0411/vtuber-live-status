CREATE TABLE IF NOT EXISTS working (
    working_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    platform TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial_success', 'failed')),
    started_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    finished_at TEXT,
    elapsed_seconds REAL,
    checked_count INTEGER NOT NULL DEFAULT 0,
    live_count INTEGER NOT NULL DEFAULT 0,
    offline_count INTEGER NOT NULL DEFAULT 0,
    snapshots_inserted INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    summary TEXT
);
