"""Section Writer Agent — writes one section of the research paper."""

from strands import Agent

from researcher.config import get_model

SECTION_WRITER_PROMPT = """You are a research paper section writer. You receive a section title, description, and relevant claims/evidence, and write that section in clear academic prose.

Write the section content as markdown. Include:
- Clear topic sentences
- Evidence-backed statements with confidence indicators where relevant
- Smooth transitions between points

Rules:
- Write 2-5 paragraphs depending on evidence density
- Cite sources by title when referencing specific claims
- Do NOT invent facts — only use the provided claims
- Use hedging language ("suggests", "indicates") for low-confidence claims
- Use definitive language ("demonstrates", "shows") for high-confidence claims
- Do not include the section title in your output (it's added separately)
"""


def create_section_writer_agent() -> Agent:
    """Create the section writer agent."""
    return Agent(
        model=get_model(),
        system_prompt=SECTION_WRITER_PROMPT,
        tools=[],
    )
