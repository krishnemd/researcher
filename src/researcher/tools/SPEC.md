# Tools Subsystem Spec

This directory-level spec complements:
- root `SPECIFICATION.md`
- `src/researcher/SPEC.md`

## Scope
- External retrieval helpers used by agents/orchestrator.

## Contract
- `ddg_search.py`
  - Must provide deterministic, query-driven web search integration.
- `web_fetch.py`
  - Must fetch and normalize page content for downstream processing.
  - Must support visited URL de-duplication behavior used by orchestrator.

## Reliability Rules
- Tool errors should be surfaced clearly and handled by callers.
- Avoid introducing non-local/runtime-external dependencies beyond existing project scope.
