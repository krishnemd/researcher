# Knowledge Subsystem Spec

This directory-level spec complements:
- root `SPECIFICATION.md`
- `src/researcher/SPEC.md`

## Scope
- Graph schema, storage, gap detection, and export.

## Schema Contract
- Node types: `Source`, `Claim`, `Question`, `Hypothesis`.
- Edge types: `supports`, `contradicts`, `answers`, `refines`, `cites`.
- Contradictions must be explicit graph relationships.

## Behavior Contract
- Graph CRUD must be deterministic and persistable.
- Confidence propagation must account for supporting/contradicting edges.
- Gap detection must expose unanswered questions, weak claims, contradictions, and isolation.
- Export must include metadata and remain consumable by external visualization/import tools.

## Module Roles
- `schema.py`: type definitions/contracts.
- `graph.py`: state, operations, propagation, persistence.
- `gaps.py`: gap report logic.
- `export.py`: graph artifact generation.
