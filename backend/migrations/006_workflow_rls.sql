-- Extend tenant RLS to workflow and generic persistence tables.
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE domain_records ENABLE ROW LEVEL SECURITY;

ALTER TABLE user_profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE reports FORCE ROW LEVEL SECURITY;
ALTER TABLE approval_requests FORCE ROW LEVEL SECURITY;
ALTER TABLE domain_records FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_profiles_policy ON user_profiles;
DROP POLICY IF EXISTS tenant_tasks_policy ON tasks;
DROP POLICY IF EXISTS tenant_reports_policy ON reports;
DROP POLICY IF EXISTS tenant_approvals_policy ON approval_requests;
DROP POLICY IF EXISTS tenant_domain_records_policy ON domain_records;

CREATE POLICY tenant_profiles_policy ON user_profiles
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_tasks_policy ON tasks
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_reports_policy ON reports
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_approvals_policy ON approval_requests
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_domain_records_policy ON domain_records
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
