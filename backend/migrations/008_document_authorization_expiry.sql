-- Preserve document authorization expiry for retrieval hard filtering.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS authorization_expires_at TIMESTAMPTZ;
