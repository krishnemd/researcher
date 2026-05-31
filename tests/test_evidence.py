import json

from researcher.evidence import Evidence, EvidenceStore


def test_evidence_store_deduplicates_by_url(tmp_path) -> None:
    store = EvidenceStore(str(tmp_path))

    e1 = Evidence(
        source_url="https://example.com/a",
        title="A",
        content_snippet="x",
        extracted_claims=["c1"],
        confidence_score=0.8,
        search_query="topic",
    )
    e2 = Evidence(
        source_url="https://example.com/a",
        title="A duplicate",
        content_snippet="y",
        extracted_claims=["c2"],
        confidence_score=0.2,
        search_query="topic",
    )

    store.add(e1)
    store.add(e2)

    assert len(store.evidence) == 1
    assert store.has_url("https://example.com/a")


def test_evidence_store_persists_and_loads(tmp_path) -> None:
    store = EvidenceStore(str(tmp_path))
    e = Evidence(
        source_url="https://example.com/b",
        title="B",
        content_snippet="snippet",
        extracted_claims=["claim"],
        confidence_score=0.6,
        search_query="topic",
    )
    store.add(e)
    store.add_gap("Need stronger evidence")

    persisted = tmp_path / "evidence.json"
    assert persisted.exists()

    raw = json.loads(persisted.read_text())
    assert len(raw["evidence"]) == 1
    assert raw["research_gaps"] == ["Need stronger evidence"]

    loaded = EvidenceStore(str(tmp_path))
    loaded.load()

    assert len(loaded.evidence) == 1
    assert loaded.evidence[0].source_url == "https://example.com/b"
    assert loaded.research_gaps == ["Need stronger evidence"]
