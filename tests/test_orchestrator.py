"""Integration tests for the orchestrator with mocked LLM agents and tools.

These tests exercise the full two-phase pipeline without any real network calls
or Ollama inference by patching the agent factories and tool functions.
"""

import contextlib
import json
from unittest.mock import MagicMock, patch

from researcher.orchestrator import Orchestrator

# ─── Canned agent responses ───────────────────────────────────────────────────

DECOMPOSE_JSON = json.dumps({
    "questions": [
        {"text": "What are the health benefits of exercise?", "priority": 1},
        {"text": "How much exercise is recommended weekly?", "priority": 2},
    ],
    "hypotheses": [
        {"text": "Regular exercise reduces cardiovascular risk", "question_index": 0},
    ],
})

EXTRACT_JSON = json.dumps({
    "source_title": "Exercise Health Study",
    "source_url": "https://example.com/exercise",
    "claims": [
        {"text": "30 minutes of exercise per day reduces heart disease risk by 35%", "confidence": 0.9},
        {"text": "Exercise improves mental health outcomes", "confidence": 0.8},
    ],
    "relationships": [],
    "answers_question": True,
})

CRITIC_JSON = json.dumps({
    "weak_claims": [],
    "new_questions": [],
    "contradictions": [],
    "should_continue": False,
    "reasoning": "Sufficient coverage achieved.",
})

OUTLINE_JSON = json.dumps({
    "title": "Benefits of Exercise: A Research Summary",
    "sections": [
        {"title": "Overview", "description": "High-level findings", "claim_ids": []},
        {"title": "Health Benefits", "description": "Physical health improvements", "claim_ids": []},
    ],
})

SEARCH_RESULT = (
    "SOURCES_FOUND:\n"
    "- Title: Exercise Health Study\n"
    "  URL: https://example.com/exercise\n"
    "  Key Content: Studies show 30 min/day reduces heart disease risk.\n"
)


def _patch_all_agents():
    """Return a list of context manager patches for all agents."""
    return [
        patch("researcher.orchestrator.create_decompose_agent", return_value=MagicMock(return_value=DECOMPOSE_JSON)),
        patch("researcher.orchestrator.create_search_agent", return_value=MagicMock(return_value=SEARCH_RESULT)),
        patch("researcher.orchestrator.create_extract_agent", return_value=MagicMock(return_value=EXTRACT_JSON)),
        patch("researcher.orchestrator.create_factcheck_agent", return_value=MagicMock(return_value="")),
        patch("researcher.orchestrator.create_critic_agent", return_value=MagicMock(return_value=CRITIC_JSON)),
        patch("researcher.paper.create_outline_agent", return_value=MagicMock(return_value=OUTLINE_JSON)),
        patch("researcher.paper.create_section_writer_agent", return_value=MagicMock(return_value="Section content.")),
        patch("researcher.orchestrator.create_leaf_agent", return_value=MagicMock(return_value="Leaf.")),
        patch("researcher.orchestrator.create_branch_agent", return_value=MagicMock(return_value="Branch.")),
        patch("researcher.orchestrator.create_root_agent", return_value=MagicMock(return_value="Root.")),
    ]


@contextlib.contextmanager
def all_agents_patched(**overrides):
    """Context manager that patches all agents; pass overrides to replace specific ones."""
    patches = _patch_all_agents()
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestOrchestratorIntegration:
    """End-to-end tests with all external I/O mocked."""

    def _make_orchestrator(self, tmp_path, time_budget: int = 3) -> Orchestrator:
        return Orchestrator(
            topic="benefits of exercise",
            time_budget_seconds=time_budget,
            output_dir=str(tmp_path),
        )

    def test_full_run_produces_artifacts(self, tmp_path):
        """A complete run should produce a paper, graph JSON, evidence JSON, and run metadata."""
        with all_agents_patched():
            orch = self._make_orchestrator(tmp_path)
            paper_path = orch.run()

        import os
        assert os.path.exists(paper_path), f"Paper not found at {paper_path}"

        # Evidence JSON must exist
        evidence_path = tmp_path / "evidence.json"
        assert evidence_path.exists(), "evidence.json not found"
        with open(evidence_path) as f:
            ev_data = json.load(f)
        assert isinstance(ev_data["evidence"], list)

        # Run metadata must exist with required fields
        run_files = list(tmp_path.glob("run_*.json"))
        assert run_files, "No run metadata file found"
        with open(run_files[0]) as f:
            meta = json.load(f)
        required_fields = [
            "topic", "model", "time_budget_seconds", "actual_time_seconds",
            "iterations", "sources_collected", "claims_extracted",
            "graph_nodes", "graph_edges", "interactive_mode", "timestamp",
        ]
        for field in required_fields:
            assert field in meta, f"Missing metadata field: {field}"
        assert meta["topic"] == "benefits of exercise"

        # Graph JSON must exist
        graph_files = list(tmp_path.glob("graph_*.json"))
        assert graph_files, "No graph JSON file found"
        with open(graph_files[0]) as f:
            graph_data = json.load(f)
        assert "nodes" in graph_data
        assert "edges" in graph_data
        assert "metadata" in graph_data

    def test_extractor_populates_graph(self, tmp_path):
        """Claims extracted by the extractor agent should end up in the knowledge graph."""
        with all_agents_patched():
            orch = self._make_orchestrator(tmp_path)
            orch.run()

        graph = orch.store.graph
        assert len(graph.claims) >= 2, f"Expected ≥2 claims, got {len(graph.claims)}"
        claim_texts = [c.text for c in graph.claims.values()]
        assert any("heart disease" in t for t in claim_texts), "Heart disease claim missing from graph"

    def test_graceful_decompose_failure(self, tmp_path):
        """If decompose fails to parse, it should fall back and still run."""
        patches = _patch_all_agents()
        # Override decompose to return invalid JSON
        patches[0] = patch(
            "researcher.orchestrator.create_decompose_agent",
            return_value=MagicMock(return_value="not valid json"),
        )
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            orch = self._make_orchestrator(tmp_path)
            paper_path = orch.run()

        import os
        assert os.path.exists(paper_path)
        assert len(orch.store.graph.questions) >= 1, "Fallback question should exist"

    def test_search_failure_degrades_gracefully(self, tmp_path):
        """If all search agents fail, the run should still complete with partial output."""
        patches = _patch_all_agents()
        # Override search to raise
        patches[1] = patch(
            "researcher.orchestrator.create_search_agent",
            return_value=MagicMock(side_effect=RuntimeError("network down")),
        )
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            orch = self._make_orchestrator(tmp_path)
            paper_path = orch.run()

        import os
        assert os.path.exists(paper_path)

    def test_resume_loads_prior_evidence(self, tmp_path):
        """Resuming should load prior evidence and not re-visit already-seen URLs."""
        with all_agents_patched():
            orch = self._make_orchestrator(tmp_path)
            orch.run()
            first_evidence_count = len(orch.store.evidence)
            first_visited_urls = set(orch.store.visited_urls)

        assert first_evidence_count > 0, "First run should collect evidence"

        with all_agents_patched():
            orch2 = Orchestrator(
                topic="benefits of exercise",
                time_budget_seconds=3,
                output_dir=str(tmp_path),
                resume=True,
            )
            # Evidence from first run should be loaded on resume
            assert len(orch2.store.evidence) == first_evidence_count
            # Visited URLs should be preserved so they aren't re-fetched
            assert orch2.store.visited_urls == first_visited_urls
