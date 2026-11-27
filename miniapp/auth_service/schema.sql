-- Apply manually to the dedicated PRIZORA PostgreSQL database before enabling the API.
-- Telegram ID is the canonical identity key shared with the existing bot.
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY CHECK (telegram_id > 0),
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    display_name TEXT,
    photo_url TEXT,
    language_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash BYTEA PRIMARY KEY,
    telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS auth_sessions_user_idx ON auth_sessions(telegram_id);
CREATE INDEX IF NOT EXISTS auth_sessions_expiry_idx ON auth_sessions(expires_at);
