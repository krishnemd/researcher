"""Paper generator - renders research as markdown.

Two modes:
1. Graph-driven (new): Uses outline agent + section writer for structured output
2. Tree-based (legacy fallback): Renders the summary tree as collapsible markdown
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

from researcher.evidence import EvidenceStore

logger = logging.getLogger(__name__)


def generate_paper(topic: str, store: EvidenceStore, tree: Optional[dict] = None) -> str:
    """Generate a research paper, preferring graph-driven approach.

    Falls back to tree-based rendering if graph-driven fails or graph is empty.

    Returns:
        Path to the saved file.
    """
    # Try graph-driven paper if graph has content
    graph = store.graph
    if graph.node_count > 0 and len(graph.claims) >= 2:
        try:
            content = _generate_graph_paper(topic, store)
            if content:
                return _save_paper(content, topic, store.output_dir)
        except Exception as e:
            logger.warning(f"Graph-driven paper failed, falling back to tree: {e}")

    # Fallback: tree-based rendering
    if tree is None:
        tree = {"root": "", "branches": [], "leaves": {}}

    content = _render_tree(topic, store, tree)
    return _save_paper(content, topic, store.output_dir)


def _save_paper(content: str, topic: str, output_dir: str) -> str:
    """Save paper content to file and return the path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)[:50]
    filename = f"research_{safe_topic.strip().replace(' ', '_')}_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w") as f:
        f.write(content)

    return filepath


def _generate_graph_paper(topic: str, store: EvidenceStore) -> Optional[str]:
    """Generate paper from knowledge graph using outline + section writer agents."""
    from researcher.agents.outline import create_outline_agent
    from researcher.agents.section_writer import create_section_writer_agent
    from researcher.agents.validation import parse_agent_output, OutlineOutput
    from researcher.knowledge.gaps import detect_gaps

    graph = store.graph
    gap_report = detect_gaps(graph)

    # Step 1: Generate outline from graph
    prompt = (
        f"Research topic: {topic}\n\n"
        f"Knowledge state:\n{graph.get_prompt_summary(max_tokens=800)}\n\n"
        f"Gaps: {gap_report.summary()}\n\n"
        f"Create a paper outline that organizes these findings."
    )

    agent = create_outline_agent()
    raw = str(agent(prompt))
    outline = parse_agent_output(raw, OutlineOutput)

    if not outline:
        return None

    # Step 2: Write sections in parallel
    sections_content: dict[int, str] = {}

    def write_section(idx: int, section) -> tuple[int, str]:
        # Gather relevant claims for this section
        relevant_claims = []
        for claim in graph.claims.values():
            # Simple text matching to assign claims to sections
            if any(word in claim.text.lower() for word in section.title.lower().split()):
                relevant_claims.append(f"[{claim.confidence:.0%}] {claim.text}")

        # If no claims matched by title, include top claims
        if not relevant_claims:
            sorted_claims = sorted(graph.claims.values(), key=lambda c: c.confidence, reverse=True)
            relevant_claims = [f"[{c.confidence:.0%}] {c.text}" for c in sorted_claims[:5]]

        section_prompt = (
            f"Research topic: {topic}\n\n"
            f"Section: {section.title}\n"
            f"Description: {section.description}\n\n"
            f"Relevant evidence:\n" + "\n".join(f"- {c}" for c in relevant_claims[:10]) + "\n\n"
            f"Write this section."
        )

        writer = create_section_writer_agent()
        return idx, str(writer(section_prompt))

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(write_section, i, sec): i
            for i, sec in enumerate(outline.sections)
        }
        for future in as_completed(futures):
            try:
                idx, content = future.result()
                sections_content[idx] = content
            except Exception as e:
                idx = futures[future]
                logger.error(f"Section {idx} write failed: {e}")
                sections_content[idx] = f"*(Section generation failed: {e})*"

    # Step 3: Assemble paper
    lines = []
    lines.append(f"# {outline.title}\n")
    lines.append(
        f"> **{len(graph.claims)}** claims from **{len(graph.sources)}** sources │ "
        f"**{len(graph.get_open_questions())}** open questions │ "
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    )
    lines.append("---\n")

    for i, section in enumerate(outline.sections):
        lines.append(f"## {section.title}\n")
        content = sections_content.get(i, "")
        if content:
            lines.append(content)
        lines.append("")

    # Add references
    if graph.sources:
        lines.append("---\n")
        lines.append("## References\n")
        lines.append("| # | Source | Confidence |")
        lines.append("|:--|:-------|:-----------|")
        for i, source in enumerate(graph.sources.values(), 1):
            bar = "█" * int(source.credibility_score * 10) + "░" * (10 - int(source.credibility_score * 10))
            lines.append(f"| {i} | [{source.title}]({source.url}) | `{bar}` {source.credibility_score:.0%} |")
        lines.append("")

    # Add open questions
    open_qs = graph.get_open_questions()
    if open_qs:
        lines.append("---\n")
        lines.append("## Open Questions\n")
        for q in open_qs:
            lines.append(f"- {q.text}")
        lines.append("")

    # Footer
    lines.append("---\n")
    lines.append(
        f"<sub>Generated by Research Agent │ "
        f"Model: {topic} │ "
        f"Graph: {graph.node_count} nodes, {graph.edge_count} edges │ "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</sub>"
    )

    return "\n".join(lines)


def _render_tree(topic: str, store: EvidenceStore, tree: dict) -> str:
    """Render the full tree as nested collapsible markdown."""
    lines = []

    # ─── Header ───
    lines.append(f"# 🔬 {topic}\n")
    lines.append(
        f"> **{len(store.evidence)}** sources collected │ "
        f"**{len(store.get_all_claims())}** claims extracted │ "
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    )
    lines.append("---\n")

    # ─── Level 2: Root (always visible) ───
    root_summary = tree.get("root", "")
    if root_summary:
        lines.append(root_summary)
    else:
        lines.append(f"Research on **{topic}** is summarized below. Click sections to expand.\n")

    lines.append("\n---\n")

    # ─── Level 1: Branches (clickable sub-topics) ───
    branches = tree.get("branches", [])
    leaves = tree.get("leaves", {})

    if branches:
        lines.append("## 📋 Sub-Topics\n")
        lines.append("*Click any section to expand. Each contains merged findings and individual source details.*\n")

        for i, branch in enumerate(branches, 1):
            theme = branch.get("theme", f"Topic {i}")
            summary = branch.get("summary", "")
            source_urls = branch.get("sources", [])
            leaf_count = branch.get("leaf_count", 0)

            # Branch node
            lines.append(f"<details>")
            lines.append(f"<summary>{'─' * 2} <strong>{_clean_theme(theme)}</strong> "
                         f"({leaf_count} sources)</summary>\n")
            lines.append(summary)
            lines.append("")

            # ─── Level 0: Leaves inside this branch ───
            branch_evidence = [e for e in store.evidence if e.source_url in source_urls]
            if branch_evidence:
                lines.append("<details>")
                lines.append(f"<summary>📄 Individual Source Summaries ({len(branch_evidence)})</summary>\n")

                for e in branch_evidence:
                    leaf_summary = leaves.get(e.source_url, "")
                    lines.append(f"<details>")
                    lines.append(f"<summary><code>{_confidence_badge(e.confidence_score)}</code> "
                                 f"{e.title}</summary>\n")
                    lines.append(f"🔗 [{e.source_url}]({e.source_url})\n")

                    if leaf_summary:
                        lines.append(leaf_summary)
                        lines.append("")

                    if e.extracted_claims:
                        lines.append("**Raw claims:**")
                        for claim in e.extracted_claims:
                            lines.append(f"- {claim}")
                        lines.append("")

                    lines.append("</details>\n")

                lines.append("</details>\n")

            lines.append("</details>\n")

    elif store.evidence:
        # No tree structure — flat list fallback
        lines.append("## 📋 Evidence\n")
        for i, e in enumerate(store.evidence, 1):
            leaf_summary = leaves.get(e.source_url, "")
            lines.append("<details>")
            lines.append(f"<summary><code>{_confidence_badge(e.confidence_score)}</code> "
                         f"[{i}] {e.title}</summary>\n")
            lines.append(f"🔗 [{e.source_url}]({e.source_url})\n")
            if leaf_summary:
                lines.append(leaf_summary)
                lines.append("")
            if e.extracted_claims:
                lines.append("**Claims:**")
                for claim in e.extracted_claims:
                    lines.append(f"- {claim}")
            lines.append("")
            lines.append("</details>\n")

    # ─── Research Gaps ───
    if store.research_gaps:
        lines.append("---\n")
        lines.append("<details>")
        lines.append("<summary>🔍 <strong>Open Research Gaps</strong></summary>\n")
        for gap in store.research_gaps:
            lines.append(f"- [ ] {gap}")
        lines.append("")
        lines.append("</details>\n")

    # ─── Reference Table ───
    if store.evidence:
        lines.append("---\n")
        lines.append("<details>")
        lines.append("<summary>📚 <strong>All References</strong></summary>\n")
        lines.append("| # | Source | Confidence |")
        lines.append("|:--|:-------|:-----------|")
        for i, e in enumerate(store.evidence, 1):
            bar = "█" * int(e.confidence_score * 10) + "░" * (10 - int(e.confidence_score * 10))
            lines.append(f"| {i} | [{e.title}]({e.source_url}) | `{bar}` {e.confidence_score:.0%} |")
        lines.append("")
        lines.append("</details>\n")

    # ─── Tree Visualization ───
    lines.append("---\n")
    lines.append("<details>")
    lines.append("<summary>🌳 <strong>Summary Tree Structure</strong></summary>\n")
    lines.append("```")
    lines.append(f"Root: {topic}")
    if branches:
        for i, branch in enumerate(branches):
            prefix = "├──" if i < len(branches) - 1 else "└──"
            lines.append(f"  {prefix} Branch: {_clean_theme(branch['theme'])}")
            source_urls = branch.get("sources", [])
            for j, url in enumerate(source_urls):
                ev = next((e for e in store.evidence if e.source_url == url), None)
                sub_prefix = "│   ├──" if j < len(source_urls) - 1 else "│   └──"
                if i == len(branches) - 1:
                    sub_prefix = "    ├──" if j < len(source_urls) - 1 else "    └──"
                title = ev.title if ev else url
                lines.append(f"  {sub_prefix} Leaf: {title[:50]}")
    else:
        for i, e in enumerate(store.evidence):
            prefix = "├──" if i < len(store.evidence) - 1 else "└──"
            lines.append(f"  {prefix} Leaf: {e.title[:50]}")
    lines.append("```\n")
    lines.append("</details>\n")

    # ─── Footer ───
    lines.append("---\n")
    lines.append(
        f"<sub>Generated by Research Agent │ "
        f"Model: gemma4:e2b (Ollama) │ "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</sub>"
    )

    return "\n".join(lines)


def _confidence_badge(score: float) -> str:
    """Render a small confidence badge."""
    if score >= 0.8:
        return f"🟢 {score:.0%}"
    elif score >= 0.5:
        return f"🟡 {score:.0%}"
    else:
        return f"🔴 {score:.0%}"


def _clean_theme(theme: str) -> str:
    """Make a theme name readable."""
    cleaned = theme.strip()
    if len(cleaned) > 60:
        cleaned = cleaned[:57] + "..."
    return cleaned.title() if cleaned == cleaned.lower() else cleaned
