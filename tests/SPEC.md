# Tests Spec

This directory-level spec complements:
- `SPECIFICATION.md`

## Scope
- Behavioral and contract verification for CLI, evidence, graph, and validation.

## Required Coverage Areas
- CLI parsing/argument behavior.
- Evidence persistence and compatibility behavior.
- Knowledge graph CRUD, persistence, confidence propagation, and gap detection.
- Agent output parsing/validation schemas.

## Rules
- Any behavior change must be accompanied by updated or new tests.
- Tests should avoid external network dependence unless explicitly integration-scoped.
- Keep tests deterministic and fast for local development.
