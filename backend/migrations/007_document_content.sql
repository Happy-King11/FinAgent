-- Persist raw text for the supported text-document ingestion path.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content TEXT NOT NULL DEFAULT '';
