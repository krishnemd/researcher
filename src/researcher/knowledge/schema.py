"""Schema definitions for knowledge graph nodes and edges."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class RelationType(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    ANSWERS = "answers"
    REFINES = "refines"
    CITES = "cites"


class QuestionStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class HypothesisStatus(str, Enum):
    SUPPORTED = "supported"
    REFUTED = "refuted"
    UNDETERMINED = "undetermined"


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Source:
    """A web source that was fetched and analyzed."""

    id: str = field(default_factory=_new_id)
    url: str = ""
    title: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    credibility_score: float = 0.5

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "fetched_at": self.fetched_at,
            "credibility_score": self.credibility_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Source":
        return cls(**data)


@dataclass
class Claim:
    """A single factual claim extracted from a source."""

    id: str = field(default_factory=_new_id)
    text: str = ""
    source_id: str = ""
    confidence: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "source_id": self.source_id,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Claim":
        return cls(**data)


@dataclass
class Question:
    """A research sub-question to investigate."""

    id: str = field(default_factory=_new_id)
    text: str = ""
    status: QuestionStatus = QuestionStatus.OPEN
    parent_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status.value,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        data = dict(data)
        data["status"] = QuestionStatus(data["status"])
        return cls(**data)


@dataclass
class Hypothesis:
    """An initial hypothesis linked to a question."""

    id: str = field(default_factory=_new_id)
    text: str = ""
    question_id: str = ""
    status: HypothesisStatus = HypothesisStatus.UNDETERMINED
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "question_id": self.question_id,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Hypothesis":
        data = dict(data)
        data["status"] = HypothesisStatus(data["status"])
        return cls(**data)


@dataclass
class Relationship:
    """A typed edge between two nodes in the graph."""

    id: str = field(default_factory=_new_id)
    source_id: str = ""
    target_id: str = ""
    relation_type: RelationType = RelationType.SUPPORTS
    weight: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "weight": self.weight,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Relationship":
        data = dict(data)
        data["relation_type"] = RelationType(data["relation_type"])
        return cls(**data)
