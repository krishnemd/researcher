"""Evidence store for collected research data."""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from researcher.knowledge.graph import KnowledgeGraph
from researcher.knowledge.schema import Source, Claim


@dataclass
class Evidence:
    """A single piece of research evidence."""

    source_url: str
    title: str
    content_snippet: str
    extracted_claims: list[str] = field(default_factory=list)
    confidence_score: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    search_query: str = ""


class EvidenceStore:
    """Manages collected evidence with JSON persistence and URL deduplication.

    Also maintains a KnowledgeGraph layer for structured representation.
    """

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = output_dir
        self.evidence: list[Evidence] = []
        self.research_gaps: list[str] = []
        self.visited_urls: set[str] = set()
        self._filepath = os.path.join(output_dir, "evidence.json")
        self._graph: Optional[KnowledgeGraph] = None
        os.makedirs(output_dir, exist_ok=True)

    @property
    def graph(self) -> KnowledgeGraph:
        """Lazily initialize the knowledge graph."""
        if self._graph is None:
            self._graph = KnowledgeGraph(self.output_dir)
        return self._graph

    def has_url(self, url: str) -> bool:
        """Check if a URL has already been researched."""
        return url in self.visited_urls

    def mark_url(self, url: str) -> None:
        """Mark a URL as visited."""
        self.visited_urls.add(url)

    def add(self, evidence: Evidence) -> None:
        """Add evidence to the store (skips duplicate URLs).

        Also syncs data into the knowledge graph layer.
        """
        if self.has_url(evidence.source_url):
            return
        self.visited_urls.add(evidence.source_url)
        self.evidence.append(evidence)

        # Sync to knowledge graph
        source = self.graph.add_source(Source(
            url=evidence.source_url,
            title=evidence.title,
            credibility_score=evidence.confidence_score,
        ))
        for claim_text in evidence.extracted_claims:
            self.graph.add_claim(Claim(
                text=claim_text,
                source_id=source.id,
                confidence=evidence.confidence_score,
            ))

        self._persist()

    def add_gap(self, gap: str) -> None:
        """Record a research gap to investigate."""
        if gap not in self.research_gaps:
            self.research_gaps.append(gap)
            self._persist()

    def remove_gap(self, gap: str) -> None:
        """Remove a research gap that has been addressed."""
        self.research_gaps = [g for g in self.research_gaps if g != gap]

    def get_visited_urls_context(self) -> str:
        """Get list of already-visited URLs for agent context."""
        if not self.visited_urls:
            return ""
        return "ALREADY RESEARCHED (do NOT fetch these URLs again):\n" + "\n".join(
            f"- {url}" for url in sorted(self.visited_urls)
        )

    def get_summary(self) -> str:
        """Get a brief summary of all collected evidence for agent context."""
        if not self.evidence:
            return "No evidence collected yet."

        lines = [f"Evidence collected: {len(self.evidence)} sources\n"]
        for i, e in enumerate(self.evidence, 1):
            claims_str = "; ".join(e.extracted_claims[:3]) if e.extracted_claims else "No claims extracted"
            lines.append(
                f"[{i}] {e.title} (confidence: {e.confidence_score:.1f})\n"
                f"    Source: {e.source_url}\n"
                f"    Claims: {claims_str}"
            )
        return "\n".join(lines)

    def get_gaps_summary(self) -> str:
        """Get a summary of research gaps."""
        if not self.research_gaps:
            return "No identified research gaps."
        return "Research gaps to investigate:\n" + "\n".join(
            f"- {gap}" for gap in self.research_gaps
        )

    def get_all_claims(self) -> list[str]:
        """Get all extracted claims across all evidence."""
        claims = []
        for e in self.evidence:
            claims.extend(e.extracted_claims)
        return claims

    def get_sources_for_paper(self) -> list[dict]:
        """Get formatted sources for the final paper."""
        return [
            {
                "title": e.title,
                "url": e.source_url,
                "claims": e.extracted_claims,
                "confidence": e.confidence_score,
            }
            for e in self.evidence
        ]

    def get_evidence_by_theme(self) -> dict[str, list[Evidence]]:
        """Group evidence by search query (rough theme grouping)."""
        themes: dict[str, list[Evidence]] = {}
        for e in self.evidence:
            key = e.search_query or "general"
            themes.setdefault(key, []).append(e)
        return themes

    def _persist(self) -> None:
        """Save evidence to JSON file."""
        data = {
            "evidence": [asdict(e) for e in self.evidence],
            "research_gaps": self.research_gaps,
            "visited_urls": sorted(self.visited_urls),
        }
        with open(self._filepath, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        """Load evidence from JSON file if it exists."""
        if os.path.exists(self._filepath):
            with open(self._filepath, "r") as f:
                data = json.load(f)
            self.evidence = [Evidence(**e) for e in data.get("evidence", [])]
            self.research_gaps = data.get("research_gaps", [])
            self.visited_urls = set(data.get("visited_urls", []))
