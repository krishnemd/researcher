"""Extractor Agent — extracts structured claims from a single source.

Evolves the analysis agent: focused on one source at a time with JSON output.
"""

from strands import Agent
from researcher.config import get_json_model

EXTRACT_SYSTEM_PROMPT = """You are a research extraction agent. You receive content from ONE web source and extract factual claims.

Given source content and the research question it relates to, extract:
1. Specific, verifiable claims from the content
2. How claims relate to each other or to known claims
3. Whether this source answers the research question

Respond ONLY with JSON in this exact format:
{
  "source_title": "Title of the source",
  "source_url": "URL if available",
  "claims": [
    {"text": "Specific factual claim", "confidence": 0.8}
  ],
  "relationships": [
    {"claim_index": 0, "relates_to": "text of related claim or question", "relation_type": "supports"}
  ],
  "answers_question": true
}

Rules:
- confidence: 0.0-1.0 based on source quality (peer-reviewed=0.9+, news=0.7, blog=0.5, opinion=0.3)
- relation_type: "supports", "contradicts", or "refines"
- Only extract claims directly stated in the source — no inference
- Be specific: "Exercise reduces heart disease risk by 30%" not "Exercise is healthy"
- Keep claims atomic: one fact per claim
- 3-8 claims per source is typical
"""


def create_extract_agent() -> Agent:
    """Create the extractor agent."""
    return Agent(
        model=get_json_model(),
        system_prompt=EXTRACT_SYSTEM_PROMPT,
        tools=[],
    )
