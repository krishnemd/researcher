"""Fact-Check Agent - verifies claims and flags contradictions."""

from strands import Agent

from researcher.config import get_model
from researcher.tools.ddg_search import ddg_search

FACTCHECK_SYSTEM_PROMPT = """You are a fact-checking agent. Your job is to verify claims found during research.

Given a list of claims with their sources, you must:
1. Identify claims that seem dubious or need verification
2. Use ddg_search to find corroborating or contradicting evidence
3. Adjust confidence scores based on what you find
4. Flag any claims that appear to be false or misleading

Respond in this structured format:

VERIFIED_CLAIMS:
- claim: [the claim]
  original_confidence: [original score]
  adjusted_confidence: [new score after verification]
  reasoning: [why you adjusted or kept the score]

FLAGGED_CLAIMS:
- claim: [the claim]
  issue: [what's wrong - contradiction, outdated, unverifiable, etc.]
  
ADDITIONAL_EVIDENCE:
- source_url: [url of corroborating source found]
  supports: [which claim it supports or contradicts]

Be skeptical but fair. Not every claim needs deep verification - focus on:
- Claims that seem surprising or counterintuitive
- Statistical claims or specific numbers
- Claims from lower-confidence sources
"""


def create_factcheck_agent() -> Agent:
    """Create and return the fact-check agent."""
    return Agent(
        model=get_model(),
        system_prompt=FACTCHECK_SYSTEM_PROMPT,
        tools=[ddg_search],
    )
