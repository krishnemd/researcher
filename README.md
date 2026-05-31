# Researcher

A time-budgeted multi-agent research system that runs local LLM orchestration with Strands Agents and Ollama.

It performs two phases:
- Phase 1: time-bounded search + analysis + fact-check loops
- Phase 2: unbounded synthesis into a structured research markdown report

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
