"""Orchestrator - two-phase research system with parallel agents.

Phase 1 (time-bounded): PhD-style cognitive loop — decompose → search → extract → critique → repeat.
Phase 2 (unbounded): Summarizer fleet builds a tree of summaries from all evidence.
"""

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from researcher.agents.analysis import create_analysis_agent
from researcher.agents.critic import create_critic_agent
from researcher.agents.decompose import create_decompose_agent
from researcher.agents.extract import create_extract_agent
from researcher.agents.factcheck import create_factcheck_agent
from researcher.agents.search import create_search_agent
from researcher.agents.synthesis import create_branch_agent, create_leaf_agent, create_root_agent
from researcher.agents.validation import (
    CriticOutput,
    DecomposerOutput,
    ExtractorOutput,
    parse_agent_output,
)
from researcher.config import MODEL_ID, SHUTDOWN_THRESHOLD
from researcher.evidence import Evidence, EvidenceStore
from researcher.knowledge.export import export_graph_json
from researcher.knowledge.gaps import detect_gaps
from researcher.knowledge.schema import (
    Hypothesis,
    Question,
    Relationship,
    RelationType,
)
from researcher.paper import generate_paper
from researcher.tools.web_fetch import set_visited_urls

logger = logging.getLogger(__name__)


class Orchestrator:
    """Two-phase orchestrator: research fleet → summarizer fleet."""

    def __init__(
        self,
        topic: str,
        time_budget_seconds: int,
        output_dir: str = "./output",
        resume: bool = False,
        interactive: bool = False,
    ):
        self.topic = topic
        self.time_budget = time_budget_seconds
        self.output_dir = output_dir
        self.interactive = interactive
        self.store = EvidenceStore(output_dir)
        self.start_time: Optional[float] = None
        self.iteration = 0

        # Resume from prior state if requested
        if resume:
            self.store.load()
            self.store.graph.load()
            logger.info(f"Resumed: {len(self.store.evidence)} evidence, "
                        f"{self.store.graph.node_count} graph nodes")

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
        # PHASE 1: Research Loop (time-bounded, PhD-style)
        # ═══════════════════════════════════════════════════════
        logger.info("╔══ PHASE 1: RESEARCH LOOP ══╗")
        logger.info(f"  Topic: {self.topic}")
        logger.info(f"  Time budget: {self.time_budget}s ({self.time_budget // 60}m)")

        # Step 0: Decompose topic into sub-questions
        self._decompose_topic()
        self._interactive_after_decompose()

        while not self.should_stop_searching():
            self.iteration += 1
            graph = self.store.graph
            logger.info(
                f"\n┌─ Iteration {self.iteration} │ "
                f"Elapsed: {self.elapsed:.0f}s │ "
                f"Remaining: {self.remaining:.0f}s │ "
                f"Evidence: {len(self.store.evidence)} │ "
                f"Graph: {graph.node_count} nodes, {graph.edge_count} edges"
            )

            try:
                self._run_research_iteration()
            except Exception as e:
                logger.error(f"  Iteration {self.iteration} failed: {e}")
                continue

            if self.should_stop_searching():
                break

            # Interactive check after iteration
            user_decision = self._interactive_after_iteration()
            if user_decision is False:
                logger.info("  ╰─ User requested stop.")
                break

            # Run critic to decide whether to continue
            if self.iteration > 1:
                should_continue = self._run_critic()
                if not should_continue:
                    logger.info("  ╰─ Critic says: sufficient coverage. Stopping early.")
                    break

        research_time = self.elapsed
        logger.info("\n╚══ PHASE 1 COMPLETE ══╝")
        logger.info(f"  Time used: {research_time:.0f}s")
        logger.info(f"  Evidence collected: {len(self.store.evidence)} sources")
        logger.info(f"  Claims extracted: {len(self.store.get_all_claims())}")
        logger.info(f"  Graph: {graph.node_count} nodes, {graph.edge_count} edges")

        # Propagate confidence based on graph relationships
        self.store.graph.propagate_confidence()

        # ═══════════════════════════════════════════════════════
        # PHASE 2: Summarizer Fleet (unbounded — runs to completion)
        # ═══════════════════════════════════════════════════════
        logger.info("\n╔══ PHASE 2: SUMMARIZER FLEET ══╗")
        logger.info("  Building tree of summaries...")

        tree = self._build_summary_tree()
        paper_path = generate_paper(self.topic, self.store, tree)

        # Export knowledge graph
        graph_path = export_graph_json(self.store.graph, self.topic, self.output_dir)
        logger.info(f"  Graph exported to: {graph_path}")

        total_time = self.elapsed
        logger.info("\n╚══ PHASE 2 COMPLETE ══╝")
        logger.info(f"  Synthesis time: {total_time - research_time:.0f}s")
        logger.info(f"  Paper saved to: {paper_path}")

        # Save run metadata
        meta_path = self._save_run_metadata()
        logger.info(f"  Metadata saved to: {meta_path}")

        return paper_path

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1: Research Fleet
    # ═══════════════════════════════════════════════════════════════

    def _run_research_iteration(self) -> None:
        """Parallel search → parallel analysis+factcheck.

        Uses question-driven prompts from the graph when available,
        falls back to broad search prompts otherwise.
        """
        # Use question-driven prompts if we have open questions
        graph = self.store.graph
        if graph.get_open_questions():
            search_prompts = self._get_question_driven_prompts()
        else:
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

        # Extraction + factcheck in parallel
        combined = "\n\n---\n\n".join(search_results)
        logger.info("  ├─ Extraction + fact-check...")

        with ThreadPoolExecutor(max_workers=2) as executor:
            extract_future = executor.submit(self._exec_extract_and_store, combined)
            factcheck_future = None
            if self.store.evidence and self.iteration > 1:
                factcheck_future = executor.submit(self._exec_factcheck_and_apply)

            try:
                extract_future.result()
            except Exception as e:
                logger.error(f"  │  Extraction error: {e}")

            if factcheck_future:
                try:
                    factcheck_future.result()
                except Exception as e:
                    logger.error(f"  │  Fact-check error: {e}")

        logger.info("  └─ Iteration complete")

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

    def _exec_extract_and_store(self, search_results: str) -> None:
        """Run the extractor agent over search results and add findings to the graph/store.

        Tries the structured extractor first (JSON output + Pydantic validation).
        Falls back to the legacy analysis agent + regex parser if extraction fails.
        """
        # Split into individual source blocks if the search agent gave us multiple
        # (separated by the "---" divider the orchestrator uses when joining results)
        source_blocks = [b.strip() for b in search_results.split("\n\n---\n\n") if b.strip()]

        any_parsed = False
        for block in source_blocks:
            prompt = (
                f"Research topic: {self.topic}\n\n"
                f"Source content:\n{block}\n\n"
                f"Extract all factual claims from this source."
            )
            try:
                agent = create_extract_agent()
                raw = str(agent(prompt))
                result = parse_agent_output(raw, ExtractorOutput)

                if result and result.claims:
                    url = result.source_url or f"unknown-{len(self.store.evidence)}"
                    title = result.source_title or url

                    # Add evidence to store (syncs to graph automatically)
                    evidence = Evidence(
                        source_url=url,
                        title=title,
                        content_snippet="",
                        extracted_claims=[c.text for c in result.claims],
                        confidence_score=sum(c.confidence for c in result.claims) / len(result.claims),
                        search_query=self.topic,
                    )
                    self.store.add(evidence)
                    logger.info(f"  │  + {title[:60]} ({len(result.claims)} claims via extractor)")

                    # Wire relationships from extractor output into the graph
                    self._apply_extractor_relationships(result)

                    # If this source answers a question, mark it resolved
                    if result.answers_question:
                        graph = self.store.graph
                        for q in graph.get_open_questions():
                            source = graph.get_source_by_url(url)
                            if source:
                                claim_ids = [
                                    c.id for c in graph.claims.values()
                                    if c.source_id == source.id
                                ]
                                if claim_ids:
                                    graph.add_relationship(Relationship(
                                        source_id=claim_ids[0],
                                        target_id=q.id,
                                        relation_type=RelationType.ANSWERS,
                                    ))
                                    graph.resolve_question(q.id)
                                    break  # Answer one open question per source

                    any_parsed = True
                else:
                    logger.warning("  │  Extractor returned no claims for block, trying fallback")
            except Exception as e:
                logger.error(f"  │  Extractor error on block: {e}")

        # Fallback: if extractor failed on all blocks, use legacy analysis agent
        if not any_parsed:
            logger.warning("  │  Extractor failed entirely — falling back to analysis agent")
            try:
                analysis_text = self._exec_analysis(search_results)
                if analysis_text:
                    self._parse_analysis(analysis_text)
            except Exception as e:
                logger.error(f"  │  Analysis fallback error: {e}")

    def _apply_extractor_relationships(self, result: ExtractorOutput) -> None:
        """Apply claim relationships from an ExtractorOutput into the knowledge graph."""
        graph = self.store.graph
        source = graph.get_source_by_url(result.source_url or "")
        if not source:
            return

        # Map claim index → graph Claim id
        claim_ids = [c.id for c in graph.claims.values() if c.source_id == source.id]

        for rel in result.relationships:
            if rel.claim_index >= len(claim_ids):
                continue
            src_claim_id = claim_ids[rel.claim_index]

            # Try to find a matching existing claim by text similarity
            target_claim = next(
                (c for c in graph.claims.values() if rel.relates_to.lower() in c.text.lower()),
                None,
            )
            if not target_claim:
                continue

            try:
                rel_type = RelationType(rel.relation_type)
            except ValueError:
                rel_type = RelationType.SUPPORTS

            graph.add_relationship(Relationship(
                source_id=src_claim_id,
                target_id=target_claim.id,
                relation_type=rel_type,
            ))

    def _exec_factcheck_and_apply(self) -> None:
        """Run fact-check agent and apply confidence adjustments to the graph."""
        recent_claims = []
        for e in self.store.evidence[-5:]:
            for claim in e.extracted_claims:
                recent_claims.append(f"- {claim} (source: {e.source_url})")
        if not recent_claims:
            return

        prompt = (
            f"Research topic: {self.topic}\n\n"
            f"Claims to verify:\n" + "\n".join(recent_claims) + "\n\n"
            "Verify the most dubious claims."
        )
        try:
            agent = create_factcheck_agent()
            factcheck_text = str(agent(prompt))
            if not factcheck_text:
                return

            # Apply confidence adjustments: parse VERIFIED_CLAIMS blocks
            # Pattern: adjusted_confidence: <float>  reasoning: <text>
            graph = self.store.graph
            for match in re.finditer(
                r"claim:\s*(.+?)\s*\n\s*original_confidence:\s*([\d.]+)\s*\n\s*adjusted_confidence:\s*([\d.]+)",
                factcheck_text,
                re.MULTILINE,
            ):
                claim_text, _, adjusted = match.groups()
                adjusted_score = min(1.0, max(0.0, float(adjusted)))
                # Find the closest matching claim in the graph and update it
                for claim in graph.claims.values():
                    if claim_text.strip().lower() in claim.text.lower():
                        old = claim.confidence
                        claim.confidence = adjusted_score
                        logger.info(f"  │  ✓ Factcheck adjusted [{old:.2f}→{adjusted_score:.2f}] {claim.text[:60]}")
                        break

            # Flag flagged claims — lower their confidence
            for match in re.finditer(
                r"FLAGGED_CLAIMS:.*?claim:\s*(.+?)\s*\n\s*issue:\s*(.+?)(?=\n\n|\Z)",
                factcheck_text,
                re.DOTALL,
            ):
                claim_text, issue = match.groups()
                for claim in graph.claims.values():
                    if claim_text.strip().lower() in claim.text.lower():
                        claim.confidence = max(0.0, claim.confidence - 0.2)
                        logger.info(f"  │  ⚠ Factcheck flagged: {claim.text[:60]} ({issue.strip()[:40]})")
                        break

            graph._persist()

        except Exception as e:
            logger.error(f"Fact-check error: {e}")

    def _exec_analysis(self, search_results: str) -> str:
        """Legacy analysis agent — kept as fallback for unstructured output."""
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
        logger.info("  └─ Level 2: Generating root summary...")
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
                    "Summarize this single source."
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
                    "Merge these into a unified sub-topic summary."
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

    # ═══════════════════════════════════════════════════════════════
    # PhD Cognitive Loop — new methods
    # ═══════════════════════════════════════════════════════════════

    def _decompose_topic(self) -> None:
        """Step 0: Break topic into sub-questions using the decomposer agent."""
        logger.info("  ├─ Decomposing topic into sub-questions...")

        graph = self.store.graph
        # Skip if questions already exist (e.g., resume mode)
        if graph.get_open_questions():
            logger.info(f"  │  Using {len(graph.get_open_questions())} existing questions")
            return

        prior_knowledge = self.store.graph.get_prompt_summary() if self.store.evidence else ""
        prompt = f"Research topic: {self.topic}"
        if prior_knowledge:
            prompt += f"\n\nPrior knowledge:\n{prior_knowledge}"

        try:
            agent = create_decompose_agent()
            raw = str(agent(prompt))
            result = parse_agent_output(raw, DecomposerOutput)

            if result:
                for sq in result.questions:
                    q = Question(text=sq.text)
                    graph.add_question(q)
                    logger.info(f"  │  ? {sq.text}")

                for hyp in result.hypotheses:
                    if hyp.question_index < len(result.questions):
                        # Link hypothesis to the corresponding question
                        q_list = list(graph.questions.values())
                        if hyp.question_index < len(q_list):
                            h = Hypothesis(text=hyp.text, question_id=q_list[hyp.question_index].id)
                            graph.add_hypothesis(h)
            else:
                # Fallback: create a single broad question
                graph.add_question(Question(text=f"What are the key aspects of {self.topic}?"))
                logger.warning("  │  Decompose failed, using fallback question")

        except Exception as e:
            logger.error(f"  │  Decompose error: {e}")
            graph.add_question(Question(text=f"What are the key aspects of {self.topic}?"))

        logger.info(f"  │  {len(graph.get_open_questions())} questions ready")

    def _run_critic(self) -> bool:
        """Run the critic agent to evaluate progress and decide next steps.

        Returns True if research should continue, False to stop.
        """
        graph = self.store.graph
        gap_report = detect_gaps(graph)

        # If no gaps at all, stop
        if not gap_report.has_gaps:
            return False

        prompt = (
            f"Research topic: {self.topic}\n\n"
            f"Current knowledge state:\n{graph.get_prompt_summary()}\n\n"
            f"Gap analysis:\n{gap_report.summary()}\n\n"
            f"Iterations so far: {self.iteration}\n"
            f"Time remaining: {self.remaining:.0f}s\n\n"
            f"Should we continue researching or is coverage sufficient?"
        )

        try:
            agent = create_critic_agent()
            raw = str(agent(prompt))
            result = parse_agent_output(raw, CriticOutput)

            if result:
                # Add new questions from critic
                for q_text in result.new_questions:
                    graph.add_question(Question(text=q_text))
                    logger.info(f"  │  + New question: {q_text[:60]}")

                # Add gaps from critic as research gaps
                for contradiction in result.contradictions:
                    self.store.add_gap(f"Contradiction: {contradiction}")

                logger.info(f"  │  Critic: {'continue' if result.should_continue else 'stop'} — {result.reasoning[:80]}")
                return result.should_continue
            else:
                # If we can't parse critic output, continue if gaps exist
                return gap_report.has_gaps

        except Exception as e:
            logger.error(f"  │  Critic error: {e}")
            return gap_report.has_gaps

    def _get_question_driven_prompts(self) -> list[str]:
        """Generate search prompts driven by open questions from the graph."""
        graph = self.store.graph
        open_questions = graph.get_open_questions()

        if not open_questions:
            # Fall back to existing prompt generation
            return self._generate_search_prompts()

        visited_urls = self.store.get_visited_urls_context()
        prompts = []

        for q in open_questions[:3]:  # Max 3 parallel searches
            prompt = (
                f"Research topic: {self.topic}\n\n"
                f"SPECIFIC QUESTION to answer: {q.text}\n\n"
                f"{visited_urls}\n\n"
                f"Search specifically to answer the above question. "
                f"Try 2 targeted queries. Fetch 1-2 new pages."
            )
            prompts.append(prompt)

        return prompts

    # ═══════════════════════════════════════════════════════════════
    # Interactive Mode
    # ═══════════════════════════════════════════════════════════════

    def _interactive_pause(self, phase: str, context: str) -> str:
        """Pause for user input in interactive mode.

        Returns user's response or 'auto' if not in interactive mode.
        """
        if not self.interactive:
            return "auto"

        print(f"\n{'─' * 60}")
        print(f"  [{phase}] {context}")
        print(f"{'─' * 60}")
        try:
            response = input("  Your input (or 'auto' to let agent decide): ").strip()
            return response if response else "auto"
        except (EOFError, KeyboardInterrupt):
            return "auto"

    def _interactive_after_decompose(self) -> None:
        """Ask user about sub-questions after decomposition."""
        if not self.interactive:
            return

        graph = self.store.graph
        questions = graph.get_open_questions()
        context = "Sub-questions I plan to investigate:\n"
        for i, q in enumerate(questions, 1):
            context += f"    {i}. {q.text}\n"
        context += "\n  Add/remove/reprioritize? (or 'auto' to proceed)"

        response = self._interactive_pause("DECOMPOSE", context)
        if response and response != "auto":
            # Add user's question as a new research question
            graph.add_question(Question(text=response))
            logger.info(f"  │  + User added question: {response}")

    def _interactive_after_iteration(self) -> Optional[bool]:
        """Ask user for direction after each iteration.

        Returns None for auto, True to continue, False to stop.
        """
        if not self.interactive:
            return None

        graph = self.store.graph
        context = (
            f"Progress: {len(self.store.evidence)} sources, "
            f"{len(graph.claims)} claims, {len(graph.get_open_questions())} open questions\n"
            f"  Time remaining: {self.remaining:.0f}s\n\n"
            f"  Options: 'continue', 'stop', 'deeper on [topic]', or 'auto'"
        )

        response = self._interactive_pause("ITERATION", context)
        if response == "stop":
            return False
        elif response == "continue" or response == "auto":
            return None
        elif response.startswith("deeper on "):
            deeper_topic = response[len("deeper on "):]
            graph.add_question(Question(text=f"What specifically about {deeper_topic}?"))
            return True
        return None

    # ═══════════════════════════════════════════════════════════════
    # Run Metadata
    # ═══════════════════════════════════════════════════════════════

    def _save_run_metadata(self) -> str:
        """Save run metadata to a JSON file."""
        import json
        from datetime import datetime

        metadata = {
            "topic": self.topic,
            "model": MODEL_ID,
            "time_budget_seconds": self.time_budget,
            "actual_time_seconds": round(self.elapsed, 1),
            "iterations": self.iteration,
            "sources_collected": len(self.store.evidence),
            "claims_extracted": len(self.store.get_all_claims()),
            "graph_nodes": self.store.graph.node_count,
            "graph_edges": self.store.graph.edge_count,
            "open_questions": len(self.store.graph.get_open_questions()),
            "interactive_mode": self.interactive,
            "timestamp": datetime.now().isoformat(),
        }

        filepath = os.path.join(
            self.output_dir,
            f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
        os.makedirs(self.output_dir, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(metadata, f, indent=2)

        return filepath

    # ═══════════════════════════════════════════════════════════════
    # Interactive Mode
    # ═══════════════════════════════════════════════════════════════

    def _interactive_pause(self, phase: str, context: str) -> str:
        """Pause for user input in interactive mode.

        Returns user's response or 'auto' if not in interactive mode.
        """
        if not self.interactive:
            return "auto"

        print(f"\n{'─' * 60}")
        print(f"  [{phase}] {context}")
        print(f"{'─' * 60}")
        try:
            response = input("  Your input (or 'auto' to let agent decide): ").strip()
            return response if response else "auto"
        except (EOFError, KeyboardInterrupt):
            return "auto"

    def _interactive_after_decompose(self) -> None:
        """Ask user about sub-questions after decomposition."""
        if not self.interactive:
            return

        graph = self.store.graph
        questions = graph.get_open_questions()
        context = "Sub-questions I plan to investigate:\n"
        for i, q in enumerate(questions, 1):
            context += f"    {i}. {q.text}\n"
        context += "\n  Add/remove/reprioritize? (or 'auto' to proceed)"

        response = self._interactive_pause("DECOMPOSE", context)
        if response and response != "auto":
            # Add user's question as a new research question
            graph.add_question(Question(text=response))
            logger.info(f"  │  + User added question: {response}")

    def _interactive_after_iteration(self) -> Optional[bool]:
        """Ask user for direction after each iteration.

        Returns None for auto, True to continue, False to stop.
        """
        if not self.interactive:
            return None

        graph = self.store.graph
        context = (
            f"Progress: {len(self.store.evidence)} sources, "
            f"{len(graph.claims)} claims, {len(graph.get_open_questions())} open questions\n"
            f"  Time remaining: {self.remaining:.0f}s\n\n"
            f"  Options: 'continue', 'stop', 'deeper on [topic]', or 'auto'"
        )

        response = self._interactive_pause("ITERATION", context)
        if response == "stop":
            return False
        elif response == "continue" or response == "auto":
            return None
        elif response.startswith("deeper on "):
            deeper_topic = response[len("deeper on "):]
            graph.add_question(Question(text=f"What specifically about {deeper_topic}?"))
            return True
        return None
