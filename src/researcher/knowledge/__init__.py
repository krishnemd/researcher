"""Knowledge graph layer for structured research representation."""

from researcher.knowledge.schema import (
    Source,
    Claim,
    Question,
    Hypothesis,
    Relationship,
    RelationType,
    QuestionStatus,
    HypothesisStatus,
)
from researcher.knowledge.graph import KnowledgeGraph
from researcher.knowledge.gaps import detect_gaps, GapReport

__all__ = [
    "Source",
    "Claim",
    "Question",
    "Hypothesis",
    "Relationship",
    "RelationType",
    "QuestionStatus",
    "HypothesisStatus",
    "KnowledgeGraph",
    "detect_gaps",
    "GapReport",
]
