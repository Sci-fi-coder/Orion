import os
import sys
import time
import math
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import requests
from sentence_transformers import SentenceTransformer, util

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Ensure parent directory is in sys.path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import call_llm

# Load SentenceTransformer model once at module level
model = SentenceTransformer("all-MiniLM-L6-v2")

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
TOP_VENUES = ["NeurIPS", "ICML", "ICLR", "CVPR", "ACL", "EMNLP", "ICCV"]


class ArXivTool:
    """Tool for ArXiv paper discovery, Semantic Scholar enrichment, and hybrid scoring."""

    def __init__(self):
        self.model = model

    def expand_query(self, topic: str) -> List[str]:
        """
        Uses call_llm to generate 6 alternative phrasings.
        Returns [original] + 6 alternatives = 7 total.
        Fallback: return [topic].
        """
        prompt = (
            f"Generate exactly 6 alternative search phrasings and related technical terms for academic papers on the topic: '{topic}'.\n"
            "Return ONLY the 6 phrases as a plain list, one phrase per line, with no numbering, bullets, or extra text."
        )
        try:
            raw_response = call_llm(prompt)
            lines = [line.strip() for line in raw_response.splitlines() if line.strip()]

            cleaned = []
            for line in lines:
                clean_line = re.sub(r"^[\d\.\-\*\•\)]+\s*", "", line).strip()
                if clean_line and clean_line.lower() != topic.lower() and clean_line not in cleaned:
                    cleaned.append(clean_line)

            alternatives = cleaned[:6]
            return [topic] + alternatives
        except Exception as e:
            print(f"[Warning] expand_query failed ({e}), using default topic.")
            return [topic]

    def search_arxiv(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Calls ArXiv API directly via requests and parses XML response.
        Returns list of dicts: arxiv_id, title, authors, abstract, year, pdf_url, categories.
        """
        url = "http://export.arxiv.org/api/query"
        formatted_query = query if query.startswith("all:") or query.startswith("ti:") else f"all:{query}"
        params = {
            "search_query": formatted_query,
            "max_results": max_results,
            "start": 0,
            "sortBy": "relevance",
        }

        papers: List[Dict[str, Any]] = []
        for attempt in range(3):
            try:
                response = requests.get(url, params=params, timeout=15)
                if response.status_code == 429:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                response.raise_for_status()

                root = ET.fromstring(response.text)
                entries = root.findall("{http://www.w3.org/2005/Atom}entry")

                for entry in entries:
                    id_elem = entry.find("{http://www.w3.org/2005/Atom}id")
                    raw_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                    base_id = raw_id.split("/")[-1]
                    arxiv_id = re.sub(r"v\d+$", "", base_id)

                    if not arxiv_id:
                        continue

                    title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
                    title = " ".join(title_elem.text.split()) if title_elem is not None and title_elem.text else ""

                    author_elems = entry.findall("{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name")
                    authors_list = [a.text.strip() for a in author_elems if a.text]
                    authors = ", ".join(authors_list)

                    summary_elem = entry.find("{http://www.w3.org/2005/Atom}summary")
                    abstract = " ".join(summary_elem.text.split()) if summary_elem is not None and summary_elem.text else ""

                    published_elem = entry.find("{http://www.w3.org/2005/Atom}published")
                    published_str = published_elem.text.strip() if published_elem is not None and published_elem.text else ""
                    try:
                        year = int(published_str[:4]) if published_str else 2026
                    except ValueError:
                        year = 2026

                    category_elems = entry.findall("{http://www.w3.org/2005/Atom}category")
                    categories = [c.attrib.get("term", "") for c in category_elems if "term" in c.attrib]

                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

                    papers.append({
                        "arxiv_id": arxiv_id,
                        "title": title,
                        "authors": authors,
                        "abstract": abstract,
                        "year": year,
                        "pdf_url": pdf_url,
                        "categories": categories,
                    })
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[Warning] search_arxiv failed for query '{query}': {e}")
                time.sleep(1.5)

        return papers

    def enrich_with_semantic_scholar(self, arxiv_id: str) -> Dict[str, Any]:
        """
        Calls Semantic Scholar API to retrieve citations and venue.
        time.sleep(1) to avoid rate limit.
        Fallback: {citations: 0, venue: ""}.
        """
        time.sleep(1)
        url = f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}"
        params = {"fields": "citationCount,venue,year"}

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                citations = data.get("citationCount") or 0
                venue = data.get("venue") or ""
                return {"citations": citations, "venue": venue}
            return {"citations": 0, "venue": ""}
        except Exception:
            return {"citations": 0, "venue": ""}

    def compute_hybrid_score(
        self,
        semantic_sim: float,
        citations: int,
        year: int,
        venue: str,
    ) -> float:
        """Computes hybrid score combining semantic similarity, citations, recency, and venue."""
        citation_score = min(1.0, math.log(citations + 1) / math.log(1000))
        recency_score = max(0.0, 1.0 - (2026 - year) / 10.0)

        venue_str = venue or ""
        if any(top_v.lower() in venue_str.lower() for top_v in TOP_VENUES):
            venue_score = 1.0
        elif venue_str:
            venue_score = 0.7
        else:
            venue_score = 0.4

        final_score = (
            0.4 * float(semantic_sim)
            + 0.3 * float(citation_score)
            + 0.2 * float(recency_score)
            + 0.1 * float(venue_score)
        )
        return float(final_score)

    def search(self, topic: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        expand_query -> search each -> deduplicate by arxiv_id ->
        enrich with semantic scholar -> compute cosine similarity with SentenceTransformer ->
        compute hybrid score -> sort -> return top max_results.
        """
        queries = self.expand_query(topic)

        raw_papers = []
        for q in queries:
            results = self.search_arxiv(q, max_results=3)
            raw_papers.extend(results)

        seen_ids = set()
        unique_papers: List[Dict[str, Any]] = []
        for paper in raw_papers:
            aid = paper["arxiv_id"]
            if aid and aid not in seen_ids:
                seen_ids.add(aid)
                unique_papers.append(paper)

        if not unique_papers:
            return []

        for paper in unique_papers:
            enriched = self.enrich_with_semantic_scholar(paper["arxiv_id"])
            paper["citations"] = enriched.get("citations", 0)
            paper["venue"] = enriched.get("venue", "")

        topic_embedding = self.model.encode(topic, convert_to_tensor=True)
        abstracts = [p.get("abstract", "") or p.get("title", "") for p in unique_papers]
        abstract_embeddings = self.model.encode(abstracts, convert_to_tensor=True)

        cos_scores = util.cos_sim(topic_embedding, abstract_embeddings)[0]

        for i, paper in enumerate(unique_papers):
            sim = float(cos_scores[i].item())
            paper["semantic_sim"] = sim
            paper["final_score"] = self.compute_hybrid_score(
                semantic_sim=sim,
                citations=paper["citations"],
                year=paper["year"],
                venue=paper["venue"],
            )

        unique_papers.sort(key=lambda x: x["final_score"], reverse=True)
        return unique_papers[:max_results]
