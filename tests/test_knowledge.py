"""Tests for the knowledge graph layer."""

import tempfile

from researcher.knowledge.export import export_graph_json
from researcher.knowledge.gaps import detect_gaps
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


class TestKnowledgeGraphCRUD:
    def _make_graph(self):
        td = tempfile.mkdtemp()
        return KnowledgeGraph(td), td

    def test_add_source(self):
        g, _ = self._make_graph()
        s = g.add_source(Source(url="https://example.com", title="Test"))
        assert s.id in g.sources
        assert g.get_source_by_url("https://example.com") is s

    def test_source_dedup(self):
        g, _ = self._make_graph()
        s1 = g.add_source(Source(url="https://example.com", title="First"))
        s2 = g.add_source(Source(url="https://example.com", title="Second"))
        assert s1.id == s2.id
        assert len(g.sources) == 1

    def test_add_claim(self):
        g, _ = self._make_graph()
        c = g.add_claim(Claim(text="Test claim", source_id="src1", confidence=0.8))
        assert c.id in g.claims

    def test_add_question(self):
        g, _ = self._make_graph()
        q = g.add_question(Question(text="What is X?"))
        assert q.id in g.questions
        assert q.status == QuestionStatus.OPEN

    def test_add_hypothesis(self):
        g, _ = self._make_graph()
        h = g.add_hypothesis(Hypothesis(text="X is Y", question_id="q1"))
        assert h.id in g.hypotheses
        assert h.status == HypothesisStatus.UNDETERMINED

    def test_add_relationship(self):
        g, _ = self._make_graph()
        r = g.add_relationship(Relationship(
            source_id="c1", target_id="c2", relation_type=RelationType.SUPPORTS
        ))
        assert len(g.relationships) == 1
        assert r.relation_type == RelationType.SUPPORTS

    def test_get_open_questions(self):
        g, _ = self._make_graph()
        g.add_question(Question(text="Q1"))
        g.add_question(Question(text="Q2", status=QuestionStatus.RESOLVED))
        assert len(g.get_open_questions()) == 1

    def test_resolve_question(self):
        g, _ = self._make_graph()
        q = g.add_question(Question(text="Q1"))
        g.resolve_question(q.id)
        assert g.questions[q.id].status == QuestionStatus.RESOLVED

    def test_get_relationships_for(self):
        g, _ = self._make_graph()
        g.add_relationship(Relationship(source_id="a", target_id="b"))
        g.add_relationship(Relationship(source_id="c", target_id="d"))
        assert len(g.get_relationships_for("a")) == 1
        assert len(g.get_relationships_for("b")) == 1
        assert len(g.get_relationships_for("x")) == 0

    def test_node_and_edge_counts(self):
        g, _ = self._make_graph()
        g.add_source(Source(url="u1"))
        g.add_claim(Claim(text="c1"))
        g.add_question(Question(text="q1"))
        g.add_hypothesis(Hypothesis(text="h1"))
        g.add_relationship(Relationship(source_id="a", target_id="b"))
        assert g.node_count == 4
        assert g.edge_count == 1


class TestConfidencePropagation:
    def test_support_boosts(self):
        g, _ = TestKnowledgeGraphCRUD()._make_graph(), None
        g = KnowledgeGraph(tempfile.mkdtemp())
        c = g.add_claim(Claim(text="claim", confidence=0.5))
        # Two supporting relationships
        g.add_relationship(Relationship(source_id="x1", target_id=c.id, relation_type=RelationType.SUPPORTS))
        g.add_relationship(Relationship(source_id="x2", target_id=c.id, relation_type=RelationType.SUPPORTS))
        g.propagate_confidence()
        assert g.claims[c.id].confidence == 0.6  # 0.5 + 2*0.05

    def test_contradiction_drops(self):
        g = KnowledgeGraph(tempfile.mkdtemp())
        c = g.add_claim(Claim(text="claim", confidence=0.7))
        g.add_relationship(Relationship(source_id="x1", target_id=c.id, relation_type=RelationType.CONTRADICTS))
        g.propagate_confidence()
        assert g.claims[c.id].confidence == 0.6  # 0.7 - 0.1

    def test_confidence_clamp(self):
        g = KnowledgeGraph(tempfile.mkdtemp())
        c = g.add_claim(Claim(text="claim", confidence=0.05))
        g.add_relationship(Relationship(source_id="x1", target_id=c.id, relation_type=RelationType.CONTRADICTS))
        g.propagate_confidence()
        assert g.claims[c.id].confidence == 0.0  # Clamped at 0


class TestGapDetection:
    def test_unanswered_questions(self):
        g = KnowledgeGraph(tempfile.mkdtemp())
        g.add_question(Question(text="Q1"))
        gaps = detect_gaps(g)
        assert len(gaps.unanswered_questions) == 1

    def test_answered_question_not_gap(self):
        g = KnowledgeGraph(tempfile.mkdtemp())
        q = g.add_question(Question(text="Q1"))
        c = g.add_claim(Claim(text="Answer"))
        g.add_relationship(Relationship(source_id=c.id, target_id=q.id, relation_type=RelationType.ANSWERS))
        gaps = detect_gaps(g)
        assert len(gaps.unanswered_questions) == 0

    def test_weak_claims(self):
        g = KnowledgeGraph(tempfile.mkdtemp())
        g.add_claim(Claim(text="weak", confidence=0.3))
        g.add_claim(Claim(text="strong", confidence=0.9))
        gaps = detect_gaps(g)
        assert len(gaps.weak_claims) == 1

    def test_contradictions(self):
        g = KnowledgeGraph(tempfile.mkdtemp())
        c1 = g.add_claim(Claim(text="A"))
        c2 = g.add_claim(Claim(text="B"))
        g.add_relationship(Relationship(source_id=c1.id, target_id=c2.id, relation_type=RelationType.CONTRADICTS))
        gaps = detect_gaps(g)
        assert len(gaps.contradictions) == 1

    def test_isolated_claims(self):
        g = KnowledgeGraph(tempfile.mkdtemp())
        g.add_claim(Claim(text="isolated"))
        gaps = detect_gaps(g)
        assert len(gaps.isolated_claims) == 1

    def test_has_gaps(self):
        g = KnowledgeGraph(tempfile.mkdtemp())
        gaps = detect_gaps(g)
        assert not gaps.has_gaps  # Empty graph has no gaps

        g.add_question(Question(text="Q"))
        gaps = detect_gaps(g)
        assert gaps.has_gaps


class TestPersistence:
    def test_save_and_load(self):
        td = tempfile.mkdtemp()
        g = KnowledgeGraph(td)
        g.add_source(Source(url="https://x.com", title="X"))
        g.add_claim(Claim(text="claim1", confidence=0.8))
        g.add_question(Question(text="Q1"))
        g.add_relationship(Relationship(source_id="a", target_id="b"))

        # Load into new instance
        g2 = KnowledgeGraph(td)
        g2.load()
        assert len(g2.sources) == 1
        assert len(g2.claims) == 1
        assert len(g2.questions) == 1
        assert len(g2.relationships) == 1


class TestExport:
    def test_export_creates_file(self):
        td = tempfile.mkdtemp()
        g = KnowledgeGraph(td)
        g.add_source(Source(url="https://x.com", title="X"))
        g.add_claim(Claim(text="C1", source_id=list(g.sources.keys())[0]))

        import json
        path = export_graph_json(g, "test topic", td)
        with open(path) as f:
            data = json.load(f)

        assert data["metadata"]["topic"] == "test topic"
        assert data["metadata"]["node_count"] == 2
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) >= 1  # At least the claim→source cite edge
