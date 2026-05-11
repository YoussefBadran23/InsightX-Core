-- ============================================================
-- InsightX — Emergency Schema Sync Script
-- Run this if Alembic migrations have not been applied.
-- All statements use IF NOT EXISTS to be safe/idempotent.
-- ============================================================

-- 1. Ensure users table has all columns from the ORM model

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS avatar_url         VARCHAR(500),
    ADD COLUMN IF NOT EXISTS widget_config      JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(10),
    ADD COLUMN IF NOT EXISTS preferred_theme    VARCHAR(20),
    ADD COLUMN IF NOT EXISTS preferred_currency VARCHAR(3),
    ADD COLUMN IF NOT EXISTS company_name       VARCHAR(255),
    ADD COLUMN IF NOT EXISTS company_logo_url   TEXT,
    ADD COLUMN IF NOT EXISTS reset_token        VARCHAR(255),
    ADD COLUMN IF NOT EXISTS reset_token_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_login_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deleted_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_active          BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Ensure indexes exist (safe to run multiple times)
CREATE INDEX IF NOT EXISTS ix_users_reset_token ON users (reset_token);
CREATE INDEX IF NOT EXISTS ix_users_is_active   ON users (is_active);
CREATE INDEX IF NOT EXISTS ix_users_deleted_at  ON users (deleted_at);
CREATE INDEX IF NOT EXISTS ix_users_role        ON users (role);

-- 3. Stamp Alembic so it thinks all migrations have been applied
-- (Run this ONLY if you are manually syncing instead of using alembic upgrade head)
-- INSERT INTO alembic_version (version_num) VALUES ('89a2bcdef123')
-- ON CONFLICT DO NOTHING;

SELECT 'Schema sync complete. All missing columns added.' AS result;
