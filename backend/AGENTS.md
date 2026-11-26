# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project overview

A FastAPI backend for an internal-pilot financial consultation Agent. The core
rule: **financial numbers are produced by deterministic code, not the LLM.** The
LLM may understand intent, explain, and synthesize, but must never calculate or
overwrite Finance Engine outputs. Vector stores are rebuildable retrieval
indexes; PostgreSQL, authorized providers, and object storage are the eventual
authorities.

## Commands

```bash
# Install (editable, with test deps)
python -m pip install -e ".[test]"

# Compile all sources (fast syntax check)
python -m compileall -q app tests scripts

# Run the full offline suite (uses the memory/dev profile)
python -m pytest -q

# Run a single test file or test
python -m pytest tests/test_runtime_contracts.py -q
python -m pytest tests/test_runtime_contracts.py::test_runtime_context_is_immutable -q

# Local stack (PostgreSQL/Redis/MinIO + API + Celery worker), from this backend directory
docker compose --env-file .env -f ../docker-compose.yml up -d --build
docker compose --env-file .env -f ../docker-compose.yml config --quiet   # CI validates this

# Apply migrations (idempotent, lexical order) and check DB reachability
python scripts/init_db.py

# Validate dev fixture data contract
python scripts/validate_data_contract.py

# Verify the append-only audit hash chain for one case (exit 0/1)
python scripts/verify_audit_chain.py <case_id>

# Health checks
curl http://localhost:8010/health/live
curl http://localhost:8010/health/ready
```

## Architecture

The code is layered with a single **composition root**: `app/application/container.py`
(`Container`). A process-wide singleton is built at import time in `app/api/deps.py`
and injected into routes via `Depends(get_container)`. All replaceable wiring —
repository backend, embedding provider, vector store, audit log, workflow records,
idempotency, runtime event bus/hooks — is decided here, keyed off `get_settings()`.

Layers (top to bottom):

- `app/api/` — FastAPI routes and request schemas. The real routes live in
  `app/api/v1/router.py`; `app/api/v1/endpoints/*.py` are thin compatibility
  re-exports. Error responses are normalized in `app/main.py` and never leak
  stack traces or internal URLs.
- `app/application/` — use cases. `ConsultationService` is the central
  synchronous orchestration path (route → classify → compliance pre-check →
  execute pipeline → post-check → completed). `Container` composes everything.
- `app/domain/` — entities (`Product`, `Document`, `ConsultationCase`) and
  enums. `ConsultationCase` is a mutable dataclass whose state changes must go
  through `ConsultationService.transition()`.
- `app/agents/` — deterministic `IntentRouter` (keyword scoring over
  `IntentRegistry` definitions), `Advisor` (LLM wrapper with fail-closed
  fallback to retrieved facts), and deterministic-DAG `supervisor` contracts.
- `app/pipelines/` — small pipelines (product explanation, knowledge
  consultation, compliance-sensitive), registered in a versioned
  `PipelineRegistry`.
- `app/finance/` — deterministic Finance Engine (`DCFEngine`, `WACCEngine`,
  comparables, scenario). Every result is a `FinanceResult` carrying
  `formula_version`, assumptions, and warnings, using `Decimal` arithmetic.
- `app/tools/` — `ToolGateway` is the only entry point for external/registered
  tools; it enforces tenant scope, entitlement, confirmation/approval, input/
  output schema, timeout, retry, circuit breaker, fallback, cache, and
  compliance. `ComplianceEngine` loads versioned JSON rules from
  `configs/compliance_rules/`.
- `app/data/` — provider `Protocol`s (list-returning, do not change their
  signatures), `FixtureDataProvider` (`source_id="dev_fixture"`, dev/test only),
  and `DataQualityGate`.
- `app/runtime/` — `RuntimeContext`, `EventBus`, `HookRunner`, failure/recovery
  policy, `CheckpointStore`, and `DataEnvelope`. Observers get safe read-only
  views; sensitive payloads are redacted.
- `app/observability/` — audit log (in-memory `AuditLog` and PostgreSQL
  `SQLAuditLog`), logging, metrics, redaction.
- `app/repositories/` — memory and SQL repositories for products/documents/
  consultations, plus `workflow.py` (domain records for profiles/tasks/reports/
  checkpoints).
- `app/infrastructure/` — database (SQLAlchemy models + session factory + RLS
  context), cache (Redis idempotency/locks), object storage (MinIO/S3), vector
  store (memory/Qdrant), queue (Celery).

## Key invariants

- **Determinism boundary.** `app/finance/` and the router/compliance engines are
  deterministic. Never let an LLM compute, alter, or override a financial number.
- **Tool Gateway only.** Registered tools and external calls go through
  `ToolGateway`. Do not bypass it; do not modify its core (tenant/entitlement/
  timeout/retry/fallback/cache semantics).
- **Tenant isolation.** SQL repositories must call
  `set_tenant_context(session, tenant_id)` before every query/mutation. Retrieval
  must hard-filter by `tenant_id`, document status, and authorization expiry; the
  vector backend is never the tenant authority.
- **Production fail-closed.** Two independent guards block unsafe production
  startup: `Settings.validate_production_safety()` in `app/core/config.py` and
  `Container.__init__` raising on `app_env == "production"`. Do not weaken either.
  `dev_fixture` and memory backends are never production data sources.
- **No irreversible actions.** No trading, fund transfer, deletion, or other
  side-effecting operations are in scope.

## Configuration

`app/core/config.py` `Settings` is Pydantic with environment aliases (mapped in
`get_settings()`, `@lru_cache`d). `.env.example` documents the full contract.
Embedding, LLM, and Qdrant credentials are independent variables and must never
be committed. `EMBEDDING_DIMENSION` must match the Qdrant collection dimension.

## Persistence and migrations

Migrations are raw, idempotent SQL in `migrations/` (e.g. `IF NOT EXISTS`,
`DROP ... IF EXISTS`), applied in lexical order by `scripts/init_db.py`. Never
reorder, edit already-shipped migrations, or drop columns. Add a new numbered
file. SQLAlchemy models in `app/infrastructure/database/models.py` must stay in
sync with these migrations.

## Audit chain

The audit log is an append-only per-case SHA-256 hash chain. The canonical hash
input is a fixed field set (`case_id`, `tenant_id`, `event_type`, `actor`,
`payload`, `prev_hash`, `created_at`); do not change that set or historical
hashes break. Payloads are redacted (`_safe_payload` in
`app/observability/audit.py`) before hashing/persistence. The SQL backend uses a
`(tenant_id, case_id, sequence_no)` ordering and a transaction-level advisory
lock to serialize first writes. An empty/nonexistent chain is invalid, not valid.

## Testing notes

`tests/conftest.py` forces the development/memory profile by setting environment
variables (`APP_ENV=development`, `PERSISTENCE_BACKEND=memory`,
`VECTOR_STORE_BACKEND=memory`, `EMBEDDING_PROVIDER=hashing`, etc.) and clearing
the settings cache. Because `Container` and `get_settings()` are cached, tests
must set environment before importing app modules. Real PostgreSQL/Qdrant/model
checks are opt-in integration tests and do not run in the default suite. Never
use real credentials or real financial data in tests.

## Design rules (from CONTRIBUTING.md)

Read `FINANCIAL_AGENT_IMPLEMENTATION.md` and `docs/` before large changes. Keep
the API/Application/Domain/Infrastructure/Agent/Pipeline/Tool boundaries intact,
and add or update tests for every behavior change — especially compliance, tenant
isolation, audit chains, and financial calculations. `FINANCIAL_AGENT_IMPLEMENTATION.md`
is the long-form implementation baseline; `docs/release-status.md` and
`docs/production-readiness.md` track remaining production blockers.
