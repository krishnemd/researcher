"""Pydantic models for validating agent JSON output + retry logic."""

import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── Decomposer output ────────────────────────────────────────

class SubQuestion(BaseModel):
    text: str
    priority: int = Field(default=1, ge=1, le=5)


class DecomposerHypothesis(BaseModel):
    text: str
    question_index: int = 0


class DecomposerOutput(BaseModel):
    questions: list[SubQuestion]
    hypotheses: list[DecomposerHypothesis] = Field(default_factory=list)


# ─── Extractor output (evolves analysis agent) ────────────────

class ExtractedClaim(BaseModel):
    text: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ExtractedRelationship(BaseModel):
    claim_index: int = 0
    relates_to: str = ""
    relation_type: str = Field(default="supports", pattern=r"^(supports|contradicts|refines)$")


class ExtractorOutput(BaseModel):
    claims: list[ExtractedClaim]
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    answers_question: bool = False
    source_title: str = ""
    source_url: str = ""


# ─── Critic output (evolves factcheck agent) ──────────────────

class CriticOutput(BaseModel):
    weak_claims: list[str] = Field(default_factory=list)
    new_questions: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    should_continue: bool = True
    reasoning: str = ""


# ─── Outline output ───────────────────────────────────────────

class OutlineSection(BaseModel):
    title: str
    description: str = ""
    claim_ids: list[str] = Field(default_factory=list)


class OutlineOutput(BaseModel):
    title: str
    sections: list[OutlineSection]


# ─── Section writer output ────────────────────────────────────

class SectionOutput(BaseModel):
    content: str
    references: list[str] = Field(default_factory=list)


# ─── Parsing + retry logic ────────────────────────────────────

def parse_agent_output(raw: str, model_class: type[BaseModel], retries: int = 2) -> Optional[BaseModel]:
    """Parse raw LLM text as JSON and validate against a Pydantic model.

    Attempts extraction with fallback strategies:
    1. Direct JSON parse
    2. Find JSON block within text (```json ... ```)
    3. Find first { ... } in text

    Returns None if all attempts fail after retries.
    """
    attempts = [raw]

    # Try to find JSON in code blocks
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{") or stripped.startswith("["):
                attempts.append(stripped)

    # Try to find raw JSON object
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        attempts.append(raw[start : end + 1])

    for attempt in attempts:
        try:
            data = json.loads(attempt)
            return model_class.model_validate(data)
        except (json.JSONDecodeError, Exception):
            continue

    logger.warning(f"Failed to parse output as {model_class.__name__}: {raw[:200]}...")
    return None
