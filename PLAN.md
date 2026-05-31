# Researcher v2 — Redesign Plan

> Read each item. Tick `[x]` to lock in. Unticked items are open for discussion.

---

## Guiding Principle: Extend, Don't Replace

- [x] Keep `EvidenceStore` — add a graph layer on top that reads/writes through it
- [x] Keep existing agents (search, analysis, factcheck, synthesis) — evolve their prompts and add new agents alongside
- [x] Keep the orchestrator's two-phase structure — enhance Phase 1 loop with question-driven iteration
- [x] Keep existing tools (`ddg_search`, `web_fetch`) — they work fine as-is
- [x] Keep current CLI interface — add new flags, don't remove existing ones
- [x] Keep output formats — add new ones alongside (graph JSON)
- [x] Refactor incrementally: each phase should leave the system in a working state

---

## Core Philosophy

- [x] Agent thinks like a PhD student: question → hypothesize → search → extract → evaluate → identify gaps → repeat
- [x] Research is driven by **gap detection** (what's missing) rather than broad repeated searching
- [x] Each iteration asks deeper, more targeted questions based on what the graph is missing
- [x] All inference stays local (gemma4:e2b via Ollama)
- [x] CLI unattended execution (run, walk away, check results later)
- [x] Dual output: exportable knowledge graph (JSON) + polished research paper (Markdown)

---

## Knowledge Representation (Hybrid Graph)

- [x] Add a knowledge graph layer on top of existing `EvidenceStore` (`src/researcher/knowledge/`)
- [x] Node types: `Source`, `Claim`, `Question`, `Hypothesis`
- [x] Edge types: `supports`, `contradicts`, `answers`, `refines`, `cites`
- [x] Each claim is a first-class entity with its own ID, confidence score, and source link
- [x] Questions track status: `open` | `resolved` | `abandoned`
- [x] Hypotheses link to questions and track: `supported` | `refuted` | `undetermined`
- [x] Confidence propagation: claims supported by multiple independent sources get boosted
- [x] Contradictions are explicitly modeled (not hidden)
- [x] Gap detection built into the graph: unanswered questions, weak claims, unresolved contradictions
- [x] In-memory graph with JSON persistence (no external database)
- [x] Graph export format compatible with visualization tools (d3, Obsidian, Neo4j import)
- [x] Keep backward-compatible `evidence.json` output (generated from graph)

---

## Research Loop (Cognitive Architecture)

- [x] **Step 1 — Decompose**: LLM breaks topic into 3-5 sub-questions + initial hypotheses
- [x] **Step 2 — Search**: One search agent per open question (parallel)
- [x] **Step 3 — Extract**: One LLM call per source, outputs structured JSON (claims + relationships)
- [x] **Step 4 — Graph Update**: Pure code (no LLM) inserts nodes/edges, propagates confidence, detects gaps
- [x] **Step 5 — Critique**: LLM reviews graph state, identifies weak spots, generates new questions
- [x] **Step 6 — Loop**: If time remains AND gaps exist → go to Step 2 with new questions
- [x] Iteration is bounded by time budget (same as current) but also by critic's `should_continue` signal
- [x] Each loop narrows focus (broad → specific) mimicking PhD literature review progression

---

## Agent Redesign

- [x] **Decomposer** (new, alongside existing): breaks topic into sub-questions + hypotheses → JSON output
- [x] **Search** (evolve existing): takes a single focused question instead of broad topic
- [x] **Extractor** (evolve `analysis.py`): better prompts + JSON structured output for claims + relationships
- [x] **Critic** (evolve `factcheck.py`): actually use its output + add gap detection + should_continue signal
- [x] **Outline** (new, alongside existing): graph structure → ordered section outline for paper
- [x] **Section Writer** (evolve leaf/branch/root synthesis): one section per call, parallel
- [x] Keep tree-of-summaries as fallback; graph-driven outline is the primary path
- [x] All agents move to JSON structured output (evolve away from free-text regex parsing)
- [x] Each agent prompt < 300 tokens system prompt
- [x] One task per agent call (no multi-task prompts)

---

## Structured Output & Reliability

- [x] Enable Ollama JSON mode for all agent calls
- [x] Pydantic models for each agent's expected output schema
- [x] Retry logic: if JSON parse fails, retry with simplified prompt (max 2 retries)
- [x] Fallback: extract what we can from malformed output rather than crashing
- [x] Prompts end with explicit JSON schema example

---

## Synthesis & Paper Generation

- [x] Paper outline derived from graph structure (questions → sections)
- [x] High-connectivity claims → key findings
- [x] Contradictions → dedicated "Debate" or "Open Questions" sections
- [x] Unanswered questions → "Future Work" section
- [x] Section writer: one LLM call per section (parallel)
- [x] Paper references specific claims from graph with confidence indicators

---

## Output Artifacts

- [x] `output/graph_<topic>_<timestamp>.json` — full knowledge graph (nodes + edges + metadata)
- [x] `output/research_<topic>_<timestamp>.md` — readable research paper
- [x] `output/evidence.json` — backward-compatible flat evidence (generated from graph)
- [x] `output/run_<timestamp>.json` — run metadata (topic, model, time, iterations, errors)

---

## Execution Modes

- [x] **One-shot mode** (default): give it a topic + time budget, walk away, get results — fully autonomous
- [x] **Interactive mode** (`--interactive` / `-i`): pauses at decision points and asks the user for direction
- [x] In interactive mode, the agent asks the user at key moments:
  - After decomposition: "Here are the sub-questions I plan to investigate. Add/remove/reprioritize?"
  - After each iteration: "Here's what I found so far. Should I go deeper on X, pivot to Y, or stop?"
  - Before synthesis: "Here's the graph summary. Any angle you want emphasized in the paper?"
- [x] Interactive prompts go to stdout; user responds via stdin (simple CLI Q&A)
- [x] Interactive mode still respects `--time` as a hard ceiling but pauses don't count against budget
- [x] One-shot mode is the current behavior enhanced with the PhD loop — no user input needed
- [x] Both modes produce the same output artifacts (graph + paper)
- [x] Interactive mode can also accept "skip" or "auto" to let the agent decide on any individual prompt

---

## CLI & UX

- [x] `--interactive` / `-i` flag: enable interactive mode
- [x] `--resume` flag: load prior graph and continue research
- [x] `--depth` presets: `quick` (5m, 1 iteration) / `standard` (30m) / `deep` (2h)
- [x] Progress output via stderr (topic, phase, iteration count, node/edge stats)
- [x] Keyboard interrupt → serialize current graph → generate partial paper
- [x] Keep existing flags: `--topic`, `--time`, `--output`, `--verbose`

---

## Robustness

- [x] Retry with exponential backoff on Ollama connection failures
- [x] Graceful degradation: if one agent fails, continue with remaining data
- [x] Claim deduplication: exact-match first, fuzzy matching later
- [x] URL deduplication (keep current approach, integrate with graph)
- [ ] Token budget awareness: graph summarizer compresses state into < 500 tokens for prompts

---

## Testing

- [x] Unit tests: graph CRUD, gap detection, confidence propagation
- [x] Unit tests: JSON validation/retry logic
- [ ] Integration test: one full run with mocked LLM responses
- [x] Verification: `researcher --topic "test" --time 5m` completes and outputs both graph + paper

---

## Scope Boundaries

- [x] **IN scope**: Local inference, knowledge graph, dual output, CLI, gap-driven iteration
- [x] **OUT of scope**: Web UI, API server, vector DB, embeddings, external databases, cloud deployment
- [x] **Deferred**: Semantic claim dedup (start exact-match), complex relationship types beyond supports/contradicts

---

## Implementation Order

- [ ] **Phase 1**: Knowledge graph layer (schema + store + gap detection + export) on top of EvidenceStore
- [ ] **Phase 2**: Structured output (JSON mode + Pydantic validation + retry)
- [ ] **Phase 3**: PhD loop (decomposer + extractor + critic + orchestrator enhancement)
- [ ] **Phase 4**: Synthesis (outline agent + section writer + paper enhancement)
- [ ] **Phase 5**: Polish (resume, presets, retry, tests, metadata)

Phases 1 and 2 can proceed in parallel. Phase 3 depends on both. Phases 4 and 5 are sequential after 3.
