# Security Policy

## Scope

This repository is a development and internal-pilot PoC. It is not an
authorized investment-advice service and must not be exposed to the public
internet in its development configuration.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability. Contact the
repository maintainer privately with a description, affected files or
endpoints, reproduction steps, and the potential impact. Do not include live
credentials or personal financial data in the report.

## Secrets

- Never commit `.env`, API keys, JWT secrets, passwords, private keys, or
  provider credentials.
- Revoke and rotate any credential that may have been exposed.
- Use repository or deployment secret storage for CI and production values.
- Qdrant, PostgreSQL, Redis, MinIO, and development authentication must not be
  exposed directly to the public internet.

## Financial and Data Safety

The system does not place trades or transfer funds. Financial data providers,
model providers, document sources, retention periods, and redistribution rights
must be reviewed before production use. User questions, portfolios, documents,
and risk profiles may contain sensitive data and require an approved privacy
and access-control policy.

## Supported Versions

Only the latest default branch is considered for security fixes while this
project remains a PoC.
