"""CLI entry point for the research system."""

import logging
import os
import re
import sys

import click

from researcher.orchestrator import Orchestrator

# Bypass tool consent prompts for automated operation
os.environ["BYPASS_TOOL_CONSENT"] = "true"


def parse_time(time_str: str) -> int:
    """Parse a time string like '30m', '1h', '90s' into seconds."""
    match = re.match(r"^(\d+)\s*(s|m|h|sec|min|hour|seconds?|minutes?|hours?)$", time_str.lower().strip())
    if not match:
        raise click.BadParameter(
            f"Invalid time format: '{time_str}'. Use formats like: 30m, 1h, 90s, 5min"
        )

    value = int(match.group(1))
    unit = match.group(2)

    if unit.startswith("s"):
        return value
    elif unit.startswith("m"):
        return value * 60
    elif unit.startswith("h"):
        return value * 3600
    else:
        return value


@click.command()
@click.option("--topic", "-t", required=True, help="Research topic to investigate")
@click.option("--time", "-T", "time_budget", required=True, help="Time budget (e.g., 30m, 1h, 90s)")
@click.option("--output", "-o", default="./output", help="Output directory for the paper")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose/debug logging")
def main(topic: str, time_budget: str, output: str, verbose: bool) -> None:
    """Research Agent - Automated evidence-based research paper generation.

    Uses local Ollama (gemma4:e2b) with DuckDuckGo search to research a topic
    within a time budget, then produces a structured Markdown paper.
    """
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("primp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("strands").setLevel(logging.WARNING if not verbose else logging.INFO)

    # Parse time budget
    try:
        budget_seconds = parse_time(time_budget)
    except click.BadParameter as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Research Agent Starting")
    click.echo(f"  Topic: {topic}")
    click.echo(f"  Time budget: {time_budget} ({budget_seconds}s)")
    click.echo(f"  Output: {output}")
    click.echo()

    # Run the orchestrator
    orchestrator = Orchestrator(
        topic=topic,
        time_budget_seconds=budget_seconds,
        output_dir=output,
    )

    try:
        paper_path = orchestrator.run()
        click.echo(f"\nDone! Paper saved to: {paper_path}")
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user. Generating paper from evidence collected so far...")
        from researcher.paper import generate_paper
        paper_path = generate_paper(topic, orchestrator.store)
        click.echo(f"Partial paper saved to: {paper_path}")
    except Exception as e:
        click.echo(f"\nFatal error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
