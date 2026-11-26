-- Preserve confirmation state required by consultation resume semantics.
ALTER TABLE consultation_cases ADD COLUMN IF NOT EXISTS confirmation_required BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE consultation_cases ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;
ALTER TABLE consultation_cases ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- Runtime audit ordering. Existing rows are assigned deterministically.
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS sequence_no INTEGER;
WITH ordered AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, case_id
               ORDER BY created_at, id
           ) AS assigned_sequence
    FROM audit_events
    WHERE sequence_no IS NULL
)
UPDATE audit_events AS events
SET sequence_no = ordered.assigned_sequence
FROM ordered
WHERE events.id = ordered.id;
UPDATE audit_events SET sequence_no = 1 WHERE sequence_no IS NULL;
ALTER TABLE audit_events ALTER COLUMN sequence_no SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_events_tenant_case_sequence
    ON audit_events (tenant_id, case_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_case_sequence
    ON audit_events (tenant_id, case_id, sequence_no);
