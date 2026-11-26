# Release status

## Eight-scene internal pilot

The consultation runtime is now constrained to eight versioned scenes: single-stock research, product explanation, financial knowledge, portfolio diagnosis, valuation analysis, financial-statement analysis, risk assessment, and compliance consultation. LangChain is not part of this phase; agents continue to use the project-owned `ToolRegistry` and `ToolGateway`.

The first implementation slice provides deterministic routing, registered pipeline contracts, pipeline tool allowlists, structured pipeline results, five risk-subject types, and a Risk Agent whose disposition is fixed by `RiskPolicyEngine`. The agent cannot override policy, compliance, data-quality failures, or Finance Engine results. Strongly typed scene inputs are now available for all eight scenes, and `valuation_analysis` executes DCF/WACC/comparables/scenario calculations only through the allowlisted `ToolGateway` tools. The remaining scenes continue to disclose missing structured inputs and do not ask the LLM to invent calculations.

## GitHub submission

The repository is suitable for a public GitHub submission as a local-development and internal-pilot PoC. The CI workflow runs compilation, tests, and Compose syntax validation. No runtime `.env` file, local database, IDE metadata, or Python cache should be committed.

Before publishing, review the staged file list and scan for credentials. Keep all runtime secrets in environment variables or a secret manager.

## Production status

This repository is **not yet a production-ready public financial service**. `APP_ENV=production` intentionally fails closed until all required production adapters are configured. Do not remove that guard.

Required before production:

- OIDC/JWT verification, issuer/audience validation, and tenant claims;
- approved data-provider contracts and licensing evidence;
- a working Qdrant Cloud vector backend selected through `VectorStore`, with tenant/status/authorization payload filters;
- a working DashScope OpenAI-compatible embedding endpoint, with a configured model and dimension matching the Qdrant collection;
- a working OpenAI-compatible LLM endpoint accepting the configured `deepseek-v4-pro` model identifier;
- production object-storage credentials and bucket policy;
- Redis availability, TLS/network policy, and distributed locking where state transitions need it;
- immutable/WORM audit retention and operational monitoring;
- finance-engine golden cases reviewed by a qualified financial expert;
- threat modeling, dependency scanning, backup/restore drills, rate limiting, and load testing;
- deployment secrets, migrations, rollback, and incident procedures.

The Docker Compose file is for local integration validation. It uses development authentication and placeholder credentials and must not be exposed to the public internet.

## Current local verification

```text
python -m compileall -q app tests scripts
python -m pytest -q
docker compose --env-file backend/.env config --quiet
```

The default local embedding provider is deterministic hashing and requires no API key. The Compose profile uses external Qdrant Cloud, an OpenAI-compatible embedding API, and an OpenAI-compatible LLM configured through runtime environment variables. Provider model IDs and the embedding dimension must be confirmed before indexing. A configured OpenAI-compatible embedding provider must be paired with a persistent vector backend before production use.
