# Researcher Specification (Baseline)

Updated: 2026-06-08

This file is the canonical product and behavior specification for the Researcher system.
When behavior changes, update this file together with tests.

## 1. Product Objective

Researcher is a local, time-budgeted, multi-agent research pipeline that:
- Performs iterative evidence collection with a PhD-style cognitive loop.
- Maintains a hybrid knowledge graph over collected evidence.
- Produces both machine-readable artifacts and a human-readable research paper.

## 2. Execution Model

### 2.1 Phase 1: Time-Bounded Research Loop

The system must execute an iterative loop bounded by a user-provided time budget:
1. Decompose topic into focused sub-questions and initial hypotheses.
2. Run question-driven searches in parallel (fallback to broad prompts if needed).
3. Analyze and extract claims from gathered material.
4. Update evidence store and knowledge graph.
5. Run critic/gap evaluation to decide continue vs stop.
6. Repeat while budget remains and stop criteria are not met.

### 2.2 Phase 2: Synthesis

After research stops, the system must synthesize output from collected evidence:
- Build a summary tree (leaf -> branch -> root summaries).
- Generate a markdown paper.
- Export graph JSON and run metadata.

## 3. Knowledge Graph Contract

### 3.1 Node Types
- Source
- Claim
- Question
- Hypothesis

### 3.2 Edge Types
- supports
- contradicts
- answers
- refines
- cites

### 3.3 Behavior Rules
- Contradictions must be represented explicitly in graph relationships.
- Open questions are first-class drivers for follow-up searches.
- Confidence propagation must adjust claim confidence based on support/contradiction relations.
- Gap detection must identify unanswered questions, weak claims, contradictions, and isolated claims.

## 4. CLI Surface

Required options:
- `--topic` / `-t`: required research topic
- `--output` / `-o`: output directory (default `./output`)
- `--resume` / `-r`: load prior graph/evidence from output directory
- `--interactive` / `-i`: pause at decision points for user guidance
- `--verbose` / `-v`: debug logging

Budget options (at least one required):
- `--time` / `-T`: explicit duration string (`90s`, `30m`, `1h`)
- `--depth` / `-d`: preset (`quick`, `standard`, `deep`)

Depth presets:
- quick: 5 minutes
- standard: 30 minutes
- deep: 2 hours

## 5. Artifact Contract

The run must generate the following outputs in the output directory:
- `evidence.json`: backward-compatible evidence store snapshot
- `graph_<topic>_<timestamp>.json`: knowledge graph export
- `research_<topic>_<timestamp>.md`: synthesized research paper
- `run_<timestamp>.json`: run metadata

Run metadata must include at least:
- topic
- model identifier
- configured time budget
- actual elapsed time
- iteration count
- source and claim counts
- graph node/edge counts
- interactive mode flag
- timestamp

## 6. Reliability and Safety Requirements

- System should degrade gracefully when individual agent calls fail.
- Keyboard interrupt should preserve partial state and generate partial output artifacts.
- Existing public behavior should remain backward-compatible unless a change is explicitly intentional and documented.

## 7. Testing Requirements

Minimum required coverage areas:
- CLI input validation (time parsing and argument behavior)
- Knowledge graph CRUD and persistence
- Confidence propagation
- Gap detection
- Agent output parsing/validation

Recommended additions:
- End-to-end integration test for orchestrator with mocked agents/tools
- Artifact schema assertions for graph and run metadata outputs

## 8. Out of Scope

- Cloud deployment and managed orchestration
- External database dependency for graph persistence
- Web UI/API server as a required runtime surface
