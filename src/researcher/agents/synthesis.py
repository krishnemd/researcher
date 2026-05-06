"""Synthesis Agents - fleet of summarizers that build a tree of knowledge."""

from strands import Agent
from researcher.config import get_model


# Level 0: Leaf summarizer — condenses a single evidence item
LEAF_PROMPT = """You are a leaf summarizer. You receive ONE piece of evidence (source + claims) and must produce a tight, factual summary.

Output format:
SUMMARY: [2-3 sentences capturing the key facts from this source]
CONFIDENCE: [High/Medium/Low]
KEY_POINTS:
- [bullet point 1]
- [bullet point 2]

Rules:
- Stick to facts from the source only
- No speculation or external knowledge
- Be extremely concise
"""


# Level 1: Branch summarizer — merges multiple leaf summaries
BRANCH_PROMPT = """You are a branch summarizer. You receive multiple leaf summaries from the same topic area and must merge them into a unified sub-topic summary.

Output format:
TOPIC: [descriptive title for this cluster of findings]
SUMMARY: [4-6 sentences merging the key points, noting where sources agree or conflict]
CONFIDENCE: [High/Medium/Low — based on agreement between sources]
KEY_FINDINGS:
- [merged finding 1]
- [merged finding 2]
- [merged finding 3]
CONFLICTS: [any contradictions between sources, or "None"]

Rules:
- Merge overlapping points into single stronger statements
- Note when multiple sources agree (increases confidence)
- Flag contradictions explicitly
- Do NOT add information not present in the leaf summaries
"""


# Level 2: Root summarizer — produces the final master overview
ROOT_PROMPT = """You are the root summarizer. You receive branch summaries covering different aspects of a research topic and must produce the definitive top-level overview.

Output format:
# [Research Topic Title]

## Executive Summary
[3-5 sentences capturing the most important findings across ALL branches]

## Key Themes
1. **[Theme 1]**: [1 sentence]
2. **[Theme 2]**: [1 sentence]
3. **[Theme 3]**: [1 sentence]

## Evidence Strength
[1-2 sentences on overall confidence, noting strongest and weakest areas]

## Open Questions
- [Unanswered question 1]
- [Unanswered question 2]

Rules:
- This is the TOP of the tree — be authoritative and concise
- Prioritize the most well-supported findings
- Acknowledge gaps honestly
- This overview should make sense on its own without expanding sub-sections
"""


def create_leaf_agent() -> Agent:
    """Leaf node: summarizes a single evidence item."""
    return Agent(model=get_model(), system_prompt=LEAF_PROMPT, tools=[])


def create_branch_agent() -> Agent:
    """Branch node: merges multiple leaf summaries into a sub-topic."""
    return Agent(model=get_model(), system_prompt=BRANCH_PROMPT, tools=[])


def create_root_agent() -> Agent:
    """Root node: produces the final top-level overview."""
    return Agent(model=get_model(), system_prompt=ROOT_PROMPT, tools=[])
