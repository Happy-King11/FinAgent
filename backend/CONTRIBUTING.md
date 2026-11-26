# Contributing

## Before Opening a Pull Request

1. Read `FINANCIAL_AGENT_IMPLEMENTATION.md` and the relevant files in `docs/`.
2. Keep the API, Application, Domain, Infrastructure, Agent, Pipeline, and Tool
   boundaries intact.
3. Add or update tests for every behavior change, especially compliance,
   tenant isolation, audit chains, and financial calculations.
4. Run:

   ```bash
   python -m compileall -q app tests scripts
   python -m pytest -q
   ```

5. Confirm that no `.env`, credential, personal financial data, generated
   database, model cache, or build artifact is included in the change.

## Design Rules

- Deterministic code produces financial numbers; an LLM may explain them but
  must not overwrite them.
- External tools are called through the Tool Gateway.
- Repositories and retrieval must enforce tenant and authorization boundaries.
- Development fixtures are not production data sources.
- Do not add trading, fund-transfer, deletion, or other irreversible actions
  without an explicit design and compliance review.

## Third-Party Code

FinRobot and other projects may be used as architectural references. Do not
copy source code, reports, datasets, logos, or trademarks without checking the
applicable license and attribution requirements.

## License

This repository does not currently include a selected license. Maintainers
must choose and add one before accepting external contributions or promising
reuse rights.
