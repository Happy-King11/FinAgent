-- Generic persistence records used by the first SQL repository adapter.
CREATE TABLE IF NOT EXISTS domain_records (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    record_type TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_domain_records_tenant_type
    ON domain_records (tenant_id, record_type);

ALTER TABLE domain_records ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_domain_records_policy ON domain_records;
CREATE POLICY tenant_domain_records_policy ON domain_records
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
