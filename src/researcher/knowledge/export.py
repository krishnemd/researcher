"""Export knowledge graph to various formats."""

import json
import os
from datetime import datetime

from researcher.knowledge.graph import KnowledgeGraph


def export_graph_json(graph: KnowledgeGraph, topic: str, output_dir: str) -> str:
    """Export graph as a JSON file with nodes and edges.

    Format is compatible with d3-force, Obsidian graph view, and Neo4j import.

    Returns:
        Path to the exported file.
    """
    nodes = []
    edges = []

    # Sources as nodes
    for s in graph.sources.values():
        nodes.append({
            "id": s.id,
            "type": "source",
            "label": s.title or s.url,
            "url": s.url,
            "credibility": s.credibility_score,
        })

    # Claims as nodes
    for c in graph.claims.values():
        nodes.append({
            "id": c.id,
            "type": "claim",
            "label": c.text[:100],
            "text": c.text,
            "confidence": c.confidence,
            "source_id": c.source_id,
        })

    # Questions as nodes
    for q in graph.questions.values():
        nodes.append({
            "id": q.id,
            "type": "question",
            "label": q.text[:100],
            "text": q.text,
            "status": q.status.value,
        })

    # Hypotheses as nodes
    for h in graph.hypotheses.values():
        nodes.append({
            "id": h.id,
            "type": "hypothesis",
            "label": h.text[:100],
            "text": h.text,
            "status": h.status.value,
            "question_id": h.question_id,
        })

    # Relationships as edges
    for r in graph.relationships:
        edges.append({
            "id": r.id,
            "source": r.source_id,
            "target": r.target_id,
            "type": r.relation_type.value,
            "weight": r.weight,
        })

    # Also add implicit claim→source edges
    for c in graph.claims.values():
        if c.source_id and c.source_id in graph.sources:
            edges.append({
                "id": f"cite_{c.id}",
                "source": c.id,
                "target": c.source_id,
                "type": "cites",
                "weight": 1.0,
            })

    data = {
        "metadata": {
            "topic": topic,
            "exported_at": datetime.now().isoformat(),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "sources": len(graph.sources),
            "claims": len(graph.claims),
            "questions": len(graph.questions),
            "hypotheses": len(graph.hypotheses),
        },
        "nodes": nodes,
        "edges": edges,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)[:50]
    filename = f"graph_{safe_topic.strip().replace(' ', '_')}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filepath
