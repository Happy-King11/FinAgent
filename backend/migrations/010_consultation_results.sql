-- Structured pipeline and deterministic risk-policy outputs for the eight-scene pilot.
ALTER TABLE consultation_cases ADD COLUMN IF NOT EXISTS result JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE consultation_cases ADD COLUMN IF NOT EXISTS risk_assessment JSONB;
