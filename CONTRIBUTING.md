# Contributing

Thank you for helping improve Home Assistant Facilioo.

1. Create a Python 3.14.2 virtual environment or run `uv sync --group dev`.
2. Make focused changes with type annotations and asynchronous I/O.
3. Run `uv run pytest`, `uv run ruff check .`, and `uv run ruff format --check .`.
4. Add tests for API/schema behavior and consumption/statistics semantics.

Tests must fully mock HTTP. Never use a productive resident account in automated tests. Do not
post credentials, tokens, personal names, addresses, real meter IDs, or unredacted API responses
in commits, fixtures, issues, or pull requests.

The Facilioo API is external and may differ by account. When reporting a schema variation, provide
the smallest anonymized example that preserves field names and types.
