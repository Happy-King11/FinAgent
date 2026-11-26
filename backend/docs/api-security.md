# API security

Business routes require a Bearer JWT. In development, `AUTH_DEV_MODE=true` creates a fixed local principal and optional `X-Dev-Tenant-Id`/`X-Dev-User-Id` headers may select a test tenant. These headers are ignored in production.

Production tokens must include `sub`, `tenant_id` (or `tenant`) and roles/scopes. Configure either `JWT_HS256_SECRET` for controlled internal deployments or `JWT_JWKS_URL` plus `JWT_ISSUER`/`JWT_AUDIENCE` for OIDC. Tenant IDs from request headers are never trusted as authentication.
