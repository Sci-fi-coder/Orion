import sys
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Insert parent directory to sys.path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import concurrent.futures
from typing import Optional, Dict, List, Any

from tools.arxiv_tool import ArXivTool
from tools.search_tool import WebSearchTool
from tools.ingest_tool import IngestTool


class ResearcherAgent:
    """Parallel search engine: queries ArXiv and/or web for all sub-questions simultaneously."""

    def __init__(self):
        self.arxiv = ArXivTool()
        self.web = WebSearchTool()
        self.ingest = IngestTool()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    # ─────────────────────────────────────────────────────────────────────────
    # Private search helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _search_arxiv_for_question(
        self, question: str, max_results: int = 5
    ) -> list[dict]:
        """Searches ArXiv for one sub-question and tags results with source_type."""
        try:
            results = self.arxiv.search(question, max_results=max_results)
            for r in results:
                r["source_type"] = "arxiv"
            return results
        except Exception as e:
            print(f"[Warning] ArXiv search failed for '{question}': {e}")
            return []

    def _search_web_for_question(self, question: str) -> list[dict]:
        """Searches the web for one sub-question and parses the returned text."""
        try:
            raw = self.web._run(question)
            if not raw or raw.startswith("Search error") or raw == "No results found.":
                return []

            parsed: list[dict] = []
            # Split on double newline to separate individual result blocks
            blocks = [b.strip() for b in raw.split("\n\n") if b.strip()]
            for block in blocks:
                entry: dict = {
                    "title": "",
                    "url": "",
                    "summary": "",
                    "source_type": "web",
                }
                for line in block.splitlines():
                    if line.startswith("Title:"):
                        entry["title"] = line[len("Title:"):].strip()
                    elif line.startswith("URL:"):
                        entry["url"] = line[len("URL:"):].strip()
                    elif line.startswith("Summary:"):
                        entry["summary"] = line[len("Summary:"):].strip()
                if entry["title"] or entry["url"]:
                    parsed.append(entry)

            return parsed
        except Exception as e:
            print(f"[Warning] Web search failed for '{question}': {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Parallel search dispatcher
    # ─────────────────────────────────────────────────────────────────────────

    def _run_searches_parallel(
        self,
        sub_questions: list[str],
        search_strategy: str,
    ) -> dict:
        """Dispatches parallel searches for all sub-questions using ThreadPoolExecutor."""
        futures_arxiv = []
        futures_web = []

        for question in sub_questions:
            if search_strategy in ("arxiv_only", "hybrid"):
                futures_arxiv.append(
                    self.executor.submit(self._search_arxiv_for_question, question, 5)
                )
            if search_strategy in ("web_only", "hybrid"):
                futures_web.append(
                    self.executor.submit(self._search_web_for_question, question)
                )

        # Collect ArXiv results — deduplicate by arxiv_id
        all_arxiv: dict[str, dict] = {}
        for f in concurrent.futures.as_completed(futures_arxiv):
            try:
                for paper in f.result():
                    aid = paper.get("arxiv_id", "")
                    if aid and aid not in all_arxiv:
                        all_arxiv[aid] = paper
                    elif not aid:
                        # No id — still include under a synthetic key
                        all_arxiv[f"_nokey_{len(all_arxiv)}"] = paper
            except Exception as e:
                print(f"[Warning] ArXiv future failed: {e}")

        # Collect web results
        all_web: list[dict] = []
        for f in concurrent.futures.as_completed(futures_web):
            try:
                all_web.extend(f.result())
            except Exception as e:
                print(f"[Warning] Web future failed: {e}")

        arxiv_list = sorted(
            all_arxiv.values(),
            key=lambda x: x.get("final_score", 0.0),
            reverse=True,
        )

        return {
            "arxiv_results": arxiv_list,
            "web_results": all_web,
            "total_arxiv": len(arxiv_list),
            "total_web": len(all_web),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Ingestion helper
    # ─────────────────────────────────────────────────────────────────────────

    def ingest_top_papers(
        self,
        arxiv_results: list[dict],
        workspace_id: int,
        max_papers: int = 5,
    ) -> list[dict]:
        """Ingests the top max_papers (by final_score) into ChromaDB."""
        top = sorted(
            arxiv_results,
            key=lambda x: x.get("final_score", 0.0),
            reverse=True,
        )[:max_papers]

        ingested_ids: set = set()
        ingested_papers: list[dict] = []

        for paper in top:
            arxiv_id = paper.get("arxiv_id", "")
            if not arxiv_id or arxiv_id in ingested_ids:
                paper["ingested"] = False
                continue

            try:
                result = self.ingest.ingest_paper(
                    arxiv_id=arxiv_id,
                    pdf_url=paper.get("pdf_url", f"https://arxiv.org/pdf/{arxiv_id}"),
                    workspace_id=workspace_id,
                    paper_metadata={
                        "title": paper.get("title", ""),
                        "authors": paper.get("authors", ""),
                        "year": paper.get("year", 0),
                    },
                )
                success = result.get("success", False)
                paper["ingested"] = success
                if success:
                    ingested_ids.add(arxiv_id)
                    ingested_papers.append(paper)
            except Exception as e:
                print(f"[Warning] Ingest failed for {arxiv_id}: {e}")
                paper["ingested"] = False

        return ingested_papers

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────────

    def run(
        self,
        plan: dict,
        workspace_id: int,
        max_papers: int = 5,
    ) -> dict:
        """Runs parallel searches, ingests top papers, and returns combined research data."""
        sub_questions: list[str] = plan.get("sub_questions", [plan.get("main_topic", "")])
        search_strategy: str = plan.get("search_strategy", "hybrid")

        search_output = self._run_searches_parallel(sub_questions, search_strategy)

        ingested = self.ingest_top_papers(
            arxiv_results=search_output["arxiv_results"],
            workspace_id=workspace_id,
            max_papers=max_papers,
        )

        return {
            "arxiv_results": search_output["arxiv_results"],
            "web_results": search_output["web_results"],
            "ingested_papers": ingested,
            "total_found": search_output["total_arxiv"],
            "workspace_id": workspace_id,
            "researcher_done": True,
        }
