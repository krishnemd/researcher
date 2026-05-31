# Researcher

A time-budgeted multi-agent research system that runs local LLM orchestration with Strands Agents and Ollama. It thinks like a PhD student: decompose → hypothesize → search → extract → critique → repeat.

It performs two phases:
- **Phase 1** (time-bounded): PhD-style cognitive loop — question-driven search, structured extraction, gap detection
- **Phase 2** (unbounded): Graph-driven synthesis into a structured research paper + knowledge graph export

## Architecture

```mermaid
flowchart TB
    subgraph CLI["CLI (click)"]
        flags["--topic  --time  --depth  --interactive  --resume  --output"]
    end

    CLI --> Orchestrator

    subgraph Orchestrator["ORCHESTRATOR"]
        subgraph Phase1["Phase 1: Research Loop (time-bounded)"]
            Decomposer["Decomposer<br/>(sub-questions + hypotheses)"]
            Search["Search Agents<br/>(parallel)"]
            Extractor["Extractor<br/>(structured claims)"]
            Critic["Critic<br/>(evaluate gaps)"]

            Decomposer --> Search
            Search --> Extractor
            Extractor -->|graph update| Critic
            Critic -->|new questions| Decomposer
            Critic -->|should_continue = false| Phase2
        end

        subgraph Phase2["Phase 2: Synthesis (unbounded)"]
            Outline["Outline Agent"]
            SectionWriter["Section Writer<br/>(parallel)"]
            Fallback["Fallback: tree-of-summaries<br/>(leaf → branch → root)"]

            Outline --> SectionWriter
            SectionWriter --> Paper1["Paper (.md)"]
            Fallback --> Paper2["Paper (.md)"]
        end
    end

    Orchestrator --> KG

    subgraph KG["KNOWLEDGE GRAPH"]
        direction LR
        Nodes["Nodes: Source | Claim | Question | Hypothesis"]
        Edges["Edges: supports | contradicts | answers | refines | cites"]
        Features["• Confidence propagation<br/>• Gap detection<br/>• JSON persistence + d3/Neo4j export"]
    end

    KG --> Output

    subgraph Output["OUTPUT ARTIFACTS"]
        paper["research_&lt;topic&gt;_&lt;ts&gt;.md"]
        graph["graph_&lt;topic&gt;_&lt;ts&gt;.json"]
        evidence["evidence.json"]
        metadata["run_&lt;ts&gt;.json"]
    end

    subgraph Tools["TOOLS & LLM"]
        direction LR
        ollama["Ollama (gemma4:e2b, local)"]
        ddg["DuckDuckGo Search"]
        fetch["Web Fetch (beautifulsoup4)"]
        strands["Strands Agents"]
    end

    Phase1 -.-> Tools
    Phase2 -.-> Tools
```

## What To Do First

If you just cloned the repo, follow these steps in order:

1. Start Ollama:

```bash
ollama serve
```

2. Pull the model used by default:

```bash
ollama pull gemma4:e2b
```

3. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

4. Install this project:

```bash
python -m pip install --upgrade pip
pip install -e .
```

5. Run a first research job:

```bash
researcher --topic "benefits of exercise" --time 10m --output ./output
```

6. Open generated artifacts:
- `output/evidence.json`
- `output/research_<topic>_<timestamp>.md`

## Features

- CLI-first workflow
- Time-budgeted iterative evidence collection
- URL de-duplication during crawling
- Structured evidence persistence in JSON
- Tree-based synthesis output with collapsible sections

## Project Structure

- `src/researcher/cli.py`: command-line entrypoint
- `src/researcher/orchestrator.py`: two-phase orchestration logic
- `src/researcher/evidence.py`: evidence model and persistence
- `src/researcher/paper.py`: markdown paper rendering
- `src/researcher/agents/`: search, analysis, fact-check, synthesis agents
- `src/researcher/tools/`: DuckDuckGo search and web fetch tools
- `output/`: generated reports and evidence artifacts

## Prerequisites

- Python 3.10+
- Ollama running locally at `http://localhost:11434`
- Model pulled in Ollama: `gemma4:e2b`

Example:

```bash
ollama serve
ollama pull gemma4:e2b
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

For development tools:

```bash
pip install pytest ruff
```

## Usage

```bash
researcher --topic "benefits of exercise" --time 30m --output ./output
```

Flags:
- `--topic`, `-t`: required research topic
- `--time`, `-T`: required time budget (examples: `90s`, `30m`, `1h`)
- `--output`, `-o`: output directory (default: `./output`)
- `--verbose`, `-v`: enable debug logs

## Development Workflow

Run tests:

```bash
pytest
```

Run lint checks:

```bash
ruff check .
```

Format imports/lint fixes (optional):

```bash
ruff check . --fix
```

## Output Artifacts

- `output/evidence.json`: collected evidence, gaps, and visited URLs
- `output/research_<topic>_<timestamp>.md`: generated report

## Troubleshooting

- `pip install -e .` fails:
	- Make sure you are in the repo root.
	- Confirm Python version is 3.10+ with `python --version`.
	- Upgrade pip first: `python -m pip install --upgrade pip`.

- `researcher: command not found`:
	- Ensure your virtual environment is active (`source .venv/bin/activate`).
	- Reinstall package: `pip install -e .`.

- Ollama connection errors:
	- Verify Ollama is running (`ollama serve`).
	- Check the default host in `src/researcher/config.py` is reachable.

- Model not found:
	- Pull the model again: `ollama pull gemma4:e2b`.

## Known Limitations

- Analysis parsing currently depends on strict structured model output
- External web content quality varies and can affect evidence confidence
- Fact-check agent output is not yet deeply integrated into confidence updates

## Roadmap (Short Term)

- Harden parser with structured JSON fallback
- Add integration tests for full orchestration path
- Add richer confidence calibration and source scoring
- Improve retry and timeout behavior for network operations
