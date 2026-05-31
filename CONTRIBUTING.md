# Contributing

## Local Setup

1. Create and activate a virtual environment.
2. Install package and dev dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Development Principles

- Keep changes focused and minimal.
- Preserve current public behavior unless intentionally changing it.
- Add or update tests for behavior changes.
- Prefer clear, explicit error handling over silent fallbacks.

## Running Quality Checks

```bash
pytest
ruff check .
```

## Test Guidelines

- Unit tests for parsing, data models, and deterministic helpers.
- Integration tests for orchestrator behavior should mock external tools.
- Avoid network-dependent tests in CI.

## Pull Request Checklist

- [ ] Tests pass locally
- [ ] Lint checks pass locally
- [ ] Documentation updated for user-visible changes
- [ ] New behavior is covered by tests
- [ ] No unrelated refactors included

## Commit Guidance

Use descriptive commit messages that explain intent and impact.

Example:

```text
Add evidence store unit tests and CI workflow
```
