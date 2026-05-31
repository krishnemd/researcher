"""Tests for agent output validation and parsing."""

from researcher.agents.validation import (
    parse_agent_output,
    DecomposerOutput,
    ExtractorOutput,
    CriticOutput,
    OutlineOutput,
    SectionOutput,
)


class TestDecomposerParsing:
    def test_valid_json(self):
        raw = '{"questions": [{"text": "What is X?", "priority": 1}], "hypotheses": []}'
        result = parse_agent_output(raw, DecomposerOutput)
        assert result is not None
        assert len(result.questions) == 1
        assert result.questions[0].text == "What is X?"

    def test_json_in_code_block(self):
        raw = 'Here is the output:\n```json\n{"questions": [{"text": "Q1", "priority": 2}], "hypotheses": []}\n```'
        result = parse_agent_output(raw, DecomposerOutput)
        assert result is not None
        assert result.questions[0].priority == 2

    def test_json_with_surrounding_text(self):
        raw = 'I think these are good questions: {"questions": [{"text": "Q", "priority": 1}]} that should work'
        result = parse_agent_output(raw, DecomposerOutput)
        assert result is not None

    def test_invalid_json_returns_none(self):
        raw = "This is not JSON at all"
        result = parse_agent_output(raw, DecomposerOutput)
        assert result is None

    def test_with_hypotheses(self):
        raw = '{"questions": [{"text": "Q1", "priority": 1}], "hypotheses": [{"text": "H1", "question_index": 0}]}'
        result = parse_agent_output(raw, DecomposerOutput)
        assert result is not None
        assert len(result.hypotheses) == 1
        assert result.hypotheses[0].question_index == 0


class TestExtractorParsing:
    def test_valid(self):
        raw = '{"source_title": "T", "source_url": "http://x", "claims": [{"text": "C1", "confidence": 0.9}], "relationships": [], "answers_question": true}'
        result = parse_agent_output(raw, ExtractorOutput)
        assert result is not None
        assert len(result.claims) == 1
        assert result.claims[0].confidence == 0.9
        assert result.answers_question is True

    def test_with_relationships(self):
        raw = '{"source_title": "T", "source_url": "http://x", "claims": [{"text": "C"}], "relationships": [{"claim_index": 0, "relates_to": "other", "relation_type": "supports"}], "answers_question": false}'
        result = parse_agent_output(raw, ExtractorOutput)
        assert result is not None
        assert len(result.relationships) == 1
        assert result.relationships[0].relation_type == "supports"

    def test_confidence_clamping(self):
        raw = '{"source_title": "T", "source_url": "u", "claims": [{"text": "C", "confidence": 1.5}], "relationships": [], "answers_question": false}'
        result = parse_agent_output(raw, ExtractorOutput)
        # Pydantic should reject confidence > 1.0
        assert result is None


class TestCriticParsing:
    def test_valid(self):
        raw = '{"weak_claims": ["c1"], "new_questions": ["q1"], "contradictions": [], "should_continue": true, "reasoning": "gaps exist"}'
        result = parse_agent_output(raw, CriticOutput)
        assert result is not None
        assert result.should_continue is True
        assert len(result.new_questions) == 1

    def test_stop_signal(self):
        raw = '{"weak_claims": [], "new_questions": [], "contradictions": [], "should_continue": false, "reasoning": "done"}'
        result = parse_agent_output(raw, CriticOutput)
        assert result is not None
        assert result.should_continue is False

    def test_minimal_valid(self):
        raw = '{"should_continue": true}'
        result = parse_agent_output(raw, CriticOutput)
        assert result is not None


class TestOutlineParsing:
    def test_valid(self):
        raw = '{"title": "Paper", "sections": [{"title": "Intro", "description": "Overview"}]}'
        result = parse_agent_output(raw, OutlineOutput)
        assert result is not None
        assert result.title == "Paper"
        assert len(result.sections) == 1
