# Source Tree Spec

This directory-level spec complements the root `SPECIFICATION.md`.

## Scope
- `src/` contains all runtime application code for the Researcher system.
- Code in this tree must preserve CLI-first operation and local inference assumptions.

## Contract
- Runtime behavior changes in `src/` must be reflected in:
  - root `SPECIFICATION.md`
  - relevant tests under `tests/`
- Public behavior compatibility should be preserved unless explicitly changed.

## Subdirectory Ownership
- `src/researcher/`: orchestration, domain logic, agents, and tools.
