"""Paper generator - renders the summary tree as collapsible markdown."""

import os
from datetime import datetime
from typing import Optional

from researcher.evidence import EvidenceStore


def generate_paper(topic: str, store: EvidenceStore, tree: Optional[dict] = None) -> str:
    """Render the summary tree as a collapsible markdown document.

    The tree has: root (top-level), branches (sub-topics), leaves (individual sources).
    Each level is a clickable expandable section in the output.

    Returns:
        Path to the saved file.
    """
    if tree is None:
        tree = {"root": "", "branches": [], "leaves": {}}

    content = _render_tree(topic, store, tree)

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)[:50]
    filename = f"research_{safe_topic.strip().replace(' ', '_')}_{timestamp}.md"
    filepath = os.path.join(store.output_dir, filename)

    with open(filepath, "w") as f:
        f.write(content)

    return filepath


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
