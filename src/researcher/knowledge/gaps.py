"""Gap detection — identifies what the knowledge graph is missing."""

from dataclasses import dataclass, field

from researcher.knowledge.graph import KnowledgeGraph
from researcher.knowledge.schema import Claim, Question, QuestionStatus


@dataclass
class GapReport:
    """Summary of what's missing in the current research state."""

    unanswered_questions: list[Question] = field(default_factory=list)
    weak_claims: list[Claim] = field(default_factory=list)
    contradictions: list[tuple[Claim, Claim]] = field(default_factory=list)
    isolated_claims: list[Claim] = field(default_factory=list)

    @property
    def has_gaps(self) -> bool:
        return bool(
            self.unanswered_questions
            or self.weak_claims
            or self.contradictions
            or self.isolated_claims
        )

    @property
    def total_gaps(self) -> int:
        return (
            len(self.unanswered_questions)
            + len(self.weak_claims)
            + len(self.contradictions)
            + len(self.isolated_claims)
        )

    def prioritized_questions(self, limit: int = 5) -> list[Question]:
        """Return the most important open questions to investigate next."""
        return self.unanswered_questions[:limit]

    def summary(self) -> str:
        """Short text summary for logging or prompts."""
        parts = []
        if self.unanswered_questions:
            parts.append(f"{len(self.unanswered_questions)} unanswered questions")
        if self.weak_claims:
            parts.append(f"{len(self.weak_claims)} weakly-supported claims")
        if self.contradictions:
            parts.append(f"{len(self.contradictions)} unresolved contradictions")
        if self.isolated_claims:
            parts.append(f"{len(self.isolated_claims)} isolated claims (no connections)")
        if not parts:
            return "No gaps detected."
        return "Gaps: " + ", ".join(parts)


def detect_gaps(graph: KnowledgeGraph) -> GapReport:
    """Analyze the graph and identify research gaps.

    Gaps are:
    - Open questions with no answering claims
    - Claims with confidence < 0.5 and no supporting evidence
    - Contradictions that haven't been resolved
    - Claims with no relationships (isolated nodes)
    """
    # Unanswered questions: open questions with no claims answering them
    unanswered = []
    for q in graph.questions.values():
        if q.status != QuestionStatus.OPEN:
            continue
        answering = graph.get_claims_answering(q.id)
        if not answering:
            unanswered.append(q)

    # Weak claims: low confidence and not well-supported
    weak = [c for c in graph.claims.values() if c.confidence < 0.5]

    # Contradictions
    contradictions = graph.get_contradictions()

    # Isolated claims: no relationships at all
    isolated = []
    for claim in graph.claims.values():
        rels = graph.get_relationships_for(claim.id)
        if not rels:
            isolated.append(claim)

    return GapReport(
        unanswered_questions=unanswered,
        weak_claims=weak,
        contradictions=contradictions,
        isolated_claims=isolated,
    )
