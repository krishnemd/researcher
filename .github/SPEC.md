# Workspace Customization Spec

This directory-level spec complements:
- `SPECIFICATION.md`

## Scope
- Copilot workspace customizations stored under `.github/`.

## Contract
- Agent and instruction files in this tree must reflect the canonical product contract in `SPECIFICATION.md`.
- Custom agent definitions should encode repository-specific business rules, not generic templates.
- Updates to major research workflow semantics should trigger updates here and in root specs.

## Current Artifacts
- `.github/agents/researcher-pattern.agent.md`: domain specialist agent for researcher-pattern work.
