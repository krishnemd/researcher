"""In-memory knowledge graph with JSON persistence."""

import json
import os
from typing import Optional

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


class KnowledgeGraph:
    """In-memory graph of research knowledge with typed nodes and edges."""

    def __init__(self, output_dir: str = "./output"):
        self.sources: dict[str, Source] = {}
        self.claims: dict[str, Claim] = {}
        self.questions: dict[str, Question] = {}
        self.hypotheses: dict[str, Hypothesis] = {}
        self.relationships: list[Relationship] = []

        self._output_dir = output_dir
        self._filepath = os.path.join(output_dir, "graph.json")
        os.makedirs(output_dir, exist_ok=True)

    # ─── Node insertion ───────────────────────────────────────

    def add_source(self, source: Source) -> Source:
        """Add a source node. Deduplicates by URL."""
        existing = self.get_source_by_url(source.url)
        if existing:
            return existing
        self.sources[source.id] = source
        self._persist()
        return source

    def add_claim(self, claim: Claim) -> Claim:
        """Add a claim node."""
        self.claims[claim.id] = claim
        self._persist()
        return claim

    def add_question(self, question: Question) -> Question:
        """Add a research question."""
        self.questions[question.id] = question
        self._persist()
        return question

    def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Add a hypothesis."""
        self.hypotheses[hypothesis.id] = hypothesis
        self._persist()
        return hypothesis

    def add_relationship(self, rel: Relationship) -> Relationship:
        """Add a relationship edge between two nodes."""
        self.relationships.append(rel)
        self._persist()
        return rel

    # ─── Queries ──────────────────────────────────────────────

    def get_source_by_url(self, url: str) -> Optional[Source]:
        for s in self.sources.values():
            if s.url == url:
                return s
        return None

    def get_claims_for_source(self, source_id: str) -> list[Claim]:
        return [c for c in self.claims.values() if c.source_id == source_id]

    def get_open_questions(self) -> list[Question]:
        return [q for q in self.questions.values() if q.status == QuestionStatus.OPEN]

    def get_relationships_for(self, node_id: str) -> list[Relationship]:
        """Get all relationships where node_id is source or target."""
        return [
            r for r in self.relationships
            if r.source_id == node_id or r.target_id == node_id
        ]

    def get_supporting_claims(self, claim_id: str) -> list[Claim]:
        """Get claims that support the given claim."""
        supporting_ids = [
            r.source_id for r in self.relationships
            if r.target_id == claim_id and r.relation_type == RelationType.SUPPORTS
        ]
        return [self.claims[cid] for cid in supporting_ids if cid in self.claims]

    def get_contradicting_claims(self, claim_id: str) -> list[Claim]:
        """Get claims that contradict the given claim."""
        contra_ids = [
            r.source_id for r in self.relationships
            if r.target_id == claim_id and r.relation_type == RelationType.CONTRADICTS
        ]
        return [self.claims[cid] for cid in contra_ids if cid in self.claims]

    def get_claims_answering(self, question_id: str) -> list[Claim]:
        """Get claims that answer a question."""
        answer_ids = [
            r.source_id for r in self.relationships
            if r.target_id == question_id and r.relation_type == RelationType.ANSWERS
        ]
        return [self.claims[cid] for cid in answer_ids if cid in self.claims]

    def get_unsupported_claims(self) -> list[Claim]:
        """Claims with no supporting relationships and low confidence."""
        supported_ids = {
            r.target_id for r in self.relationships
            if r.relation_type == RelationType.SUPPORTS
        }
        return [
            c for c in self.claims.values()
            if c.id not in supported_ids and c.confidence < 0.7
        ]

    def get_contradictions(self) -> list[tuple[Claim, Claim]]:
        """Get pairs of claims that contradict each other."""
        pairs = []
        for r in self.relationships:
            if r.relation_type == RelationType.CONTRADICTS:
                src = self.claims.get(r.source_id)
                tgt = self.claims.get(r.target_id)
                if src and tgt:
                    pairs.append((src, tgt))
        return pairs

    # ─── Confidence propagation ───────────────────────────────

    def propagate_confidence(self) -> None:
        """Boost claims supported by multiple independent sources.

        Simple rule: for each supporting relationship from a different source,
        nudge confidence up. For contradictions, nudge down.
        """
        for claim in self.claims.values():
            support_count = sum(
                1 for r in self.relationships
                if r.target_id == claim.id and r.relation_type == RelationType.SUPPORTS
            )
            contradict_count = sum(
                1 for r in self.relationships
                if r.target_id == claim.id and r.relation_type == RelationType.CONTRADICTS
            )

            # Each independent support boosts by 0.05, each contradiction drops by 0.1
            adjustment = (support_count * 0.05) - (contradict_count * 0.1)
            claim.confidence = max(0.0, min(1.0, claim.confidence + adjustment))

        self._persist()

    # ─── Status updates ───────────────────────────────────────

    def resolve_question(self, question_id: str) -> None:
        if question_id in self.questions:
            self.questions[question_id].status = QuestionStatus.RESOLVED
            self._persist()

    def abandon_question(self, question_id: str) -> None:
        if question_id in self.questions:
            self.questions[question_id].status = QuestionStatus.ABANDONED
            self._persist()

    def update_hypothesis_status(self, hypothesis_id: str, status: HypothesisStatus) -> None:
        if hypothesis_id in self.hypotheses:
            self.hypotheses[hypothesis_id].status = status
            self._persist()

    # ─── Summary for prompts ──────────────────────────────────

    def get_prompt_summary(self, max_tokens: int = 500) -> str:
        """Compress graph state into a short text for LLM prompts."""
        lines = []
        lines.append(f"Knowledge: {len(self.claims)} claims, {len(self.sources)} sources, "
                     f"{len(self.questions)} questions ({len(self.get_open_questions())} open)")

        # Top claims by confidence
        sorted_claims = sorted(self.claims.values(), key=lambda c: c.confidence, reverse=True)
        lines.append("\nTop claims:")
        for c in sorted_claims[:5]:
            lines.append(f"  [{c.confidence:.1f}] {c.text[:80]}")

        # Open questions
        open_qs = self.get_open_questions()
        if open_qs:
            lines.append("\nOpen questions:")
            for q in open_qs[:5]:
                lines.append(f"  - {q.text[:80]}")

        # Contradictions
        contras = self.get_contradictions()
        if contras:
            lines.append(f"\nContradictions: {len(contras)} found")
            for a, b in contras[:2]:
                lines.append(f"  * \"{a.text[:40]}\" vs \"{b.text[:40]}\"")

        summary = "\n".join(lines)
        # Rough token estimate: 4 chars per token
        if len(summary) > max_tokens * 4:
            summary = summary[: max_tokens * 4] + "\n..."
        return summary

    # ─── Stats ────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self.sources) + len(self.claims) + len(self.questions) + len(self.hypotheses)

    @property
    def edge_count(self) -> int:
        return len(self.relationships)

    # ─── Persistence ──────────────────────────────────────────

    def _persist(self) -> None:
        data = {
            "sources": [s.to_dict() for s in self.sources.values()],
            "claims": [c.to_dict() for c in self.claims.values()],
            "questions": [q.to_dict() for q in self.questions.values()],
            "hypotheses": [h.to_dict() for h in self.hypotheses.values()],
            "relationships": [r.to_dict() for r in self.relationships],
        }
        with open(self._filepath, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load graph from JSON if file exists."""
        if not os.path.exists(self._filepath):
            return
        with open(self._filepath, "r") as f:
            data = json.load(f)
        self.sources = {s["id"]: Source.from_dict(s) for s in data.get("sources", [])}
        self.claims = {c["id"]: Claim.from_dict(c) for c in data.get("claims", [])}
        self.questions = {q["id"]: Question.from_dict(q) for q in data.get("questions", [])}
        self.hypotheses = {h["id"]: Hypothesis.from_dict(h) for h in data.get("hypotheses", [])}
        self.relationships = [Relationship.from_dict(r) for r in data.get("relationships", [])]
