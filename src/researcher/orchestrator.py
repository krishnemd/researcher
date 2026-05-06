"""Orchestrator - two-phase research system with parallel agents.

Phase 1 (time-bounded): Research fleet searches + analyzes until time runs out.
Phase 2 (unbounded): Summarizer fleet builds a tree of summaries from all evidence.
"""

import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from researcher.config import SHUTDOWN_THRESHOLD
from researcher.evidence import Evidence, EvidenceStore
from researcher.agents.search import create_search_agent
from researcher.agents.analysis import create_analysis_agent
from researcher.agents.synthesis import create_leaf_agent, create_branch_agent, create_root_agent
from researcher.agents.factcheck import create_factcheck_agent
from researcher.tools.web_fetch import set_visited_urls
from researcher.paper import generate_paper

logger = logging.getLogger(__name__)


class Orchestrator:
    """Two-phase orchestrator: research fleet → summarizer fleet."""

    def __init__(self, topic: str, time_budget_seconds: int, output_dir: str = "./output"):
        self.topic = topic
        self.time_budget = time_budget_seconds
        self.output_dir = output_dir
        self.store = EvidenceStore(output_dir)
        self.start_time: Optional[float] = None
        self.iteration = 0

    @property
    def elapsed(self) -> float:
        if self.start_time is None:
            return 0
        return time.time() - self.start_time

    @property
    def remaining(self) -> float:
        return max(0, self.time_budget - self.elapsed)

    @property
    def progress(self) -> float:
        if self.time_budget == 0:
            return 1.0
        return min(1.0, self.elapsed / self.time_budget)

    def should_stop_searching(self) -> bool:
        return self.progress >= SHUTDOWN_THRESHOLD

    def run(self) -> str:
        """Run both phases. Returns path to the generated paper."""
        self.start_time = time.time()
        set_visited_urls(self.store.visited_urls)

        # ═══════════════════════════════════════════════════════
        # PHASE 1: Research Fleet (time-bounded)
        # ═══════════════════════════════════════════════════════
        logger.info(f"╔══ PHASE 1: RESEARCH FLEET ══╗")
        logger.info(f"  Topic: {self.topic}")
        logger.info(f"  Time budget: {self.time_budget}s ({self.time_budget // 60}m)")

        while not self.should_stop_searching():
            self.iteration += 1
            logger.info(
                f"\n┌─ Iteration {self.iteration} │ "
                f"Elapsed: {self.elapsed:.0f}s │ "
                f"Remaining: {self.remaining:.0f}s │ "
                f"Evidence: {len(self.store.evidence)} │ "
                f"URLs: {len(self.store.visited_urls)}"
            )

            try:
                self._run_research_iteration()
            except Exception as e:
                logger.error(f"  Iteration {self.iteration} failed: {e}")
                continue

            if self.should_stop_searching():
                break

        research_time = self.elapsed
        logger.info(f"\n╚══ PHASE 1 COMPLETE ══╝")
        logger.info(f"  Time used: {research_time:.0f}s")
        logger.info(f"  Evidence collected: {len(self.store.evidence)} sources")
        logger.info(f"  Claims extracted: {len(self.store.get_all_claims())}")

        # ═══════════════════════════════════════════════════════
        # PHASE 2: Summarizer Fleet (unbounded — runs to completion)
        # ═══════════════════════════════════════════════════════
        logger.info(f"\n╔══ PHASE 2: SUMMARIZER FLEET ══╗")
        logger.info(f"  Building tree of summaries...")

        tree = self._build_summary_tree()
        paper_path = generate_paper(self.topic, self.store, tree)

        total_time = self.elapsed
        logger.info(f"\n╚══ PHASE 2 COMPLETE ══╝")
        logger.info(f"  Synthesis time: {total_time - research_time:.0f}s")
        logger.info(f"  Paper saved to: {paper_path}")
        return paper_path

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1: Research Fleet
    # ═══════════════════════════════════════════════════════════════

    def _run_research_iteration(self) -> None:
        """Parallel search → parallel analysis+factcheck."""
        search_prompts = self._generate_search_prompts()

        logger.info(f"  ├─ Launching {len(search_prompts)} search agents...")
        search_results = []

        with ThreadPoolExecutor(max_workers=len(search_prompts)) as executor:
            futures = {
                executor.submit(self._exec_search, p): i
                for i, p in enumerate(search_prompts)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    if result:
                        search_results.append(result)
                        logger.info(f"  │  ✓ Search agent {idx+1} done")
                except Exception as e:
                    logger.error(f"  │  ✗ Search agent {idx+1}: {e}")

        if not search_results:
            return

        if self.should_stop_searching():
            return

        # Analysis + factcheck in parallel
        combined = "\n\n---\n\n".join(search_results)
        logger.info(f"  ├─ Analysis + fact-check...")

        with ThreadPoolExecutor(max_workers=2) as executor:
            analysis_future = executor.submit(self._exec_analysis, combined)
            factcheck_future = None
            if self.store.evidence and self.iteration > 1:
                factcheck_future = executor.submit(self._exec_factcheck)

            try:
                analysis_text = analysis_future.result()
                if analysis_text:
                    self._parse_analysis(analysis_text)
            except Exception as e:
                logger.error(f"  │  Analysis error: {e}")

            if factcheck_future:
                try:
                    factcheck_future.result()
                except Exception as e:
                    logger.error(f"  │  Fact-check error: {e}")

        logger.info(f"  └─ Iteration complete")

    def _generate_search_prompts(self) -> list[str]:
        """Generate parallel search prompts with different angles."""
        gaps_context = self.store.get_gaps_summary()
        evidence_summary = self.store.get_summary()
        visited_urls = self.store.get_visited_urls_context()

        base = (
            f"Research topic: {self.topic}\n\n"
            f"Current evidence:\n{evidence_summary}\n\n"
            f"{gaps_context}\n\n"
            f"{visited_urls}\n\n"
        )

        prompts = [
            base + "Search BROADLY for overview information. Try 2 general queries. Fetch 1-2 new pages.",
            base + "Search for SPECIFIC data, studies, or expert takes. Try niche angles. Fetch 1-2 new pages.",
        ]

        if self.store.research_gaps:
            prompts.append(
                base + "Fill these gaps:\n"
                + "\n".join(f"- {g}" for g in self.store.research_gaps[:3])
                + "\nSearch specifically for these."
            )

        return prompts

    def _exec_search(self, prompt: str) -> str:
        try:
            agent = create_search_agent()
            return str(agent(prompt))
        except Exception as e:
            logger.error(f"Search agent error: {e}")
            return ""

    def _exec_analysis(self, search_results: str) -> str:
        prompt = (
            f"Research topic: {self.topic}\n\n"
            f"Raw search results:\n{search_results}\n\n"
            f"Extract claims, assess credibility, identify gaps."
        )
        try:
            agent = create_analysis_agent()
            return str(agent(prompt))
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return ""

    def _exec_factcheck(self) -> str:
        recent_claims = []
        for e in self.store.evidence[-5:]:
            for claim in e.extracted_claims:
                recent_claims.append(f"- {claim} (source: {e.source_url})")
        if not recent_claims:
            return ""
        prompt = (
            f"Research topic: {self.topic}\n\n"
            f"Claims to verify:\n" + "\n".join(recent_claims) + "\n\n"
            f"Verify the most dubious claims."
        )
        try:
            agent = create_factcheck_agent()
            return str(agent(prompt))
        except Exception as e:
            logger.error(f"Fact-check error: {e}")
            return ""

    # ═══════════════════════════════════════════════════════════════
    # PHASE 2: Summarizer Fleet — Tree of Summaries
    # ═══════════════════════════════════════════════════════════════

    def _build_summary_tree(self) -> dict:
        """Build a multi-level summary tree.

        Tree structure:
            Root (master overview)
            ├── Branch 1 (sub-topic summary)
            │   ├── Leaf 1a (individual source summary)
            │   └── Leaf 1b
            ├── Branch 2
            │   ├── Leaf 2a
            │   └── Leaf 2b
            └── ...

        Returns a dict representing the tree.
        """
        if not self.store.evidence:
            return {"root": "No evidence collected.", "branches": []}

        # Level 0: Generate leaf summaries (parallel)
        logger.info(f"  ├─ Level 0: Summarizing {len(self.store.evidence)} sources (leaves)...")
        leaf_summaries = self._generate_leaves()

        # Group leaves into branches by theme
        themes = self.store.get_evidence_by_theme()
        branches = []

        # Level 1: Merge leaves into branch summaries (parallel)
        logger.info(f"  ├─ Level 1: Merging into {len(themes)} branches...")
        branch_results = self._generate_branches(themes, leaf_summaries)
        branches = branch_results

        # Level 2: Merge branches into root summary
        logger.info(f"  └─ Level 2: Generating root summary...")
        root_summary = self._generate_root(branches)

        return {
            "root": root_summary,
            "branches": branches,
            "leaves": leaf_summaries,
        }

    def _generate_leaves(self) -> dict[str, str]:
        """Level 0: Summarize each evidence item in parallel. Returns {url: summary}."""
        leaf_summaries: dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for e in self.store.evidence:
                prompt = (
                    f"Source: {e.title}\n"
                    f"URL: {e.source_url}\n"
                    f"Claims:\n" + "\n".join(f"- {c}" for c in e.extracted_claims) + "\n\n"
                    f"Summarize this single source."
                )
                futures[executor.submit(self._exec_leaf, prompt)] = e.source_url

            for future in as_completed(futures):
                url = futures[future]
                try:
                    leaf_summaries[url] = future.result()
                except Exception as e:
                    logger.error(f"  │  Leaf failed for {url}: {e}")
                    leaf_summaries[url] = "(summary unavailable)"

        logger.info(f"  │  ✓ {len(leaf_summaries)} leaf summaries generated")
        return leaf_summaries

    def _generate_branches(
        self, themes: dict[str, list], leaf_summaries: dict[str, str]
    ) -> list[dict]:
        """Level 1: Merge leaf summaries by theme in parallel."""
        branches: list[dict] = []

        with ThreadPoolExecutor(max_workers=min(4, len(themes))) as executor:
            futures = {}
            for theme_name, evidence_list in themes.items():
                # Gather leaf summaries for this theme
                leaves_for_theme = []
                for e in evidence_list:
                    leaf = leaf_summaries.get(e.source_url, "")
                    if leaf:
                        leaves_for_theme.append(f"[{e.title}]: {leaf}")

                prompt = (
                    f"Theme: {theme_name}\n"
                    f"Main topic: {self.topic}\n\n"
                    f"Leaf summaries to merge:\n" + "\n\n".join(leaves_for_theme) + "\n\n"
                    f"Merge these into a unified sub-topic summary."
                )
                futures[executor.submit(self._exec_branch, prompt)] = (theme_name, evidence_list)

            for future in as_completed(futures):
                theme_name, evidence_list = futures[future]
                try:
                    summary = future.result()
                    branches.append({
                        "theme": theme_name,
                        "summary": summary,
                        "sources": [e.source_url for e in evidence_list],
                        "leaf_count": len(evidence_list),
                    })
                    logger.info(f"  │  ✓ Branch '{theme_name}' done ({len(evidence_list)} leaves)")
                except Exception as e:
                    logger.error(f"  │  Branch '{theme_name}' failed: {e}")

        return branches

    def _generate_root(self, branches: list[dict]) -> str:
        """Level 2: Generate root summary from all branches."""
        if not branches:
            return "No branch summaries available."

        branch_text = "\n\n---\n\n".join(
            f"### {b['theme']}\n{b['summary']}" for b in branches
        )

        prompt = (
            f"Research topic: {self.topic}\n\n"
            f"Branch summaries ({len(branches)} sub-topics):\n\n{branch_text}\n\n"
            f"Create the definitive top-level overview."
        )

        try:
            agent = create_root_agent()
            return str(agent(prompt))
        except Exception as e:
            logger.error(f"Root synthesis failed: {e}")
            return f"Research on '{self.topic}' covered {len(branches)} sub-topics."

    def _exec_leaf(self, prompt: str) -> str:
        agent = create_leaf_agent()
        return str(agent(prompt))

    def _exec_branch(self, prompt: str) -> str:
        agent = create_branch_agent()
        return str(agent(prompt))

    # ═══════════════════════════════════════════════════════════════
    # Parsing
    # ═══════════════════════════════════════════════════════════════

    def _parse_analysis(self, analysis_text: str) -> None:
        """Parse structured analysis output and add evidence to the store."""
        entries_match = re.findall(
            r"source_url:\s*(.+?)\n\s*title:\s*(.+?)\n\s*claims:\s*\n((?:\s*-\s*.+\n)*)\s*confidence:\s*([\d.]+)",
            analysis_text,
            re.MULTILINE,
        )

        for url, title, claims_block, confidence in entries_match:
            claims = re.findall(r"-\s*(.+)", claims_block)
            evidence = Evidence(
                source_url=url.strip(),
                title=title.strip(),
                content_snippet="",
                extracted_claims=[c.strip() for c in claims],
                confidence_score=min(1.0, max(0.0, float(confidence))),
                search_query=self.topic,
            )
            self.store.add(evidence)
            logger.info(f"  │  + {title.strip()} ({len(claims)} claims)")

        gaps_section = re.search(r"RESEARCH_GAPS:\s*\n((?:\s*-\s*.+\n)*)", analysis_text)
        if gaps_section:
            gaps = re.findall(r"-\s*(.+)", gaps_section.group(1))
            for gap in gaps:
                self.store.add_gap(gap.strip())
