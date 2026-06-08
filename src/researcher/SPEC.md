# Core Package Spec

This directory-level spec complements:
- root `SPECIFICATION.md`
- `src/SPEC.md`

## Scope
- Core package entry points and orchestration logic.
- Evidence store, paper generation, and configuration.

## Module Contracts
- `cli.py`
  - Must enforce budget input contract (`--time` or `--depth`).
  - Must pass mode/resume/output settings through to orchestrator.
- `orchestrator.py`
  - Must keep two-phase execution semantics.
  - Phase 1 must be time-bounded and gap/question-driven.
  - Phase 2 must synthesize outputs and emit artifacts.
- `evidence.py`
  - Must preserve backward-compatible evidence persistence (`evidence.json`).
- `paper.py`
  - Must render a readable markdown report from collected/synthesized evidence.
- `config.py`
  - Runtime thresholds/config defaults must remain explicit and deterministic.

## Artifact Expectations
- Writes/coordinates generation of:
  - `evidence.json`
  - `graph_<topic>_<timestamp>.json`
  - `research_<topic>_<timestamp>.md`
  - `run_<timestamp>.json`
