"""Decomposer Agent — breaks a topic into sub-questions and hypotheses."""

from strands import Agent
from researcher.config import get_json_model

DECOMPOSE_SYSTEM_PROMPT = """You are a PhD research advisor. Your job is to break a research topic into focused, investigable sub-questions.

Given a topic (and optionally prior knowledge), produce:
1. 3-5 specific sub-questions that together cover the topic
2. For each question, an initial hypothesis (what you expect to find)

Respond ONLY with JSON in this exact format:
{
  "questions": [
    {"text": "What is ...?", "priority": 1}
  ],
  "hypotheses": [
    {"text": "I expect that ...", "question_index": 0}
  ]
}

Rules:
- priority: 1 (highest) to 5 (lowest)
- question_index refers to the position in the questions array (0-based)
- Questions should be specific enough to search for, not vague
- Prefer questions that can be answered with evidence from web sources
- If prior knowledge is provided, ask questions that fill gaps rather than repeat what's known
"""


def create_decompose_agent() -> Agent:
    """Create the decomposer agent."""
    return Agent(
        model=get_json_model(),
        system_prompt=DECOMPOSE_SYSTEM_PROMPT,
        tools=[],
    )
