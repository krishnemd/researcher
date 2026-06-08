# Agents Subsystem Spec

This directory-level spec complements:
- root `SPECIFICATION.md`
- `src/researcher/SPEC.md`

## Scope
- Agent constructors/prompts for decomposition, search, extraction, critique, and synthesis.

## Behavioral Rules
- Each agent should be single-purpose and output-focused.
- Prefer structured JSON outputs where parser models exist.
- Prompt changes must preserve downstream parser compatibility.
- Agent failures should degrade gracefully in orchestrator flow.

## Role Mapping
- `decompose.py`: creates sub-questions and hypotheses.
- `search.py`: runs focused retrieval for topic/questions.
- `extract.py` and `analysis.py`: derive claims and structured evidence.
- `critic.py` and `factcheck.py`: identify weaknesses/contradictions and continuation signals.
- `outline.py`, `section_writer.py`, `synthesis.py`: synthesis path for final paper content.
- `validation.py`: schema and parse reliability boundary.
