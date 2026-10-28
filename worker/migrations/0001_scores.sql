CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    owner_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    character TEXT NOT NULL,
    mode TEXT NOT NULL,
    score INTEGER NOT NULL,
    seconds INTEGER NOT NULL,
    wave INTEGER NOT NULL,
    kills INTEGER NOT NULL,
    level INTEGER NOT NULL,
    bosses INTEGER NOT NULL,
    difficulty REAL NOT NULL,
    swarm_seconds INTEGER NOT NULL,
    victory INTEGER NOT NULL,
    version TEXT NOT NULL,
    seed INTEGER,
    replay TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scores_rank ON scores (mode, character, score DESC, seconds ASC);
CREATE INDEX IF NOT EXISTS idx_scores_owner ON scores (owner_hash);
