# Compliance rules

The initial frozen rule asset is `guaranteed_return_ban.json`; the corresponding deterministic PoC implementation is `app.tools.compliance.DEFAULT_RULES`.

Production promotion should load all versioned JSON files from this directory and execute their `test_cases` in CI. A rule update must change its version and pass its regression cases before release.
