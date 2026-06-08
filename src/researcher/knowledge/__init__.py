"""Knowledge graph layer for structured research representation."""

from researcher.knowledge.gaps import GapReport, detect_gaps
from researcher.knowledge.graph import KnowledgeGraph
from researcher.knowledge.schema import (
    Claim,
    Hypothesis,
    HypothesisStatus,
    Question,
    QuestionStatus,
    Relationship,
    RelationType,
    Source,
)

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
