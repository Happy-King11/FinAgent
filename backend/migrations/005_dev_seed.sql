-- Development-only seed rows required by the local demo profile.
INSERT INTO tenants (id, name, status, policy_version)
VALUES ('tenant-demo', 'Local Demo Tenant', 'active', '1.0.0')
ON CONFLICT (id) DO NOTHING;

INSERT INTO users (id, tenant_id, subject_id, roles, status)
VALUES ('dev-user', 'tenant-demo', 'dev-user', '["admin", "user"]'::jsonb, 'active')
ON CONFLICT (tenant_id, subject_id) DO UPDATE SET id = EXCLUDED.id, roles = EXCLUDED.roles, status = EXCLUDED.status;
