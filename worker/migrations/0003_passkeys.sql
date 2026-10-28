-- Paket K: passkeys (Face ID / Touch ID / Windows Hello) and their one-time challenges.
CREATE TABLE IF NOT EXISTS passkeys (
    credential_id TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL,
    public_key TEXT NOT NULL,
    alg INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS challenges (
    id TEXT PRIMARY KEY,
    challenge TEXT NOT NULL,
    purpose TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);
