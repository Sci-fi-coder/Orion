import sys
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Insert parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz  # pymupdf
import requests
import re
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter


class IngestTool:
    """Downloads ArXiv PDFs, parses into section-aware chunks, and stores in ChromaDB."""

    def __init__(self):
        # Load embedding model
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        # ChromaDB Persistent Client & Collection
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.chroma_client.get_or_create_collection(name="orion_papers")

        # Text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=50,
        )

        # PDF cache directory
        self.pdf_cache = Path("./pdf_cache")
        self.pdf_cache.mkdir(parents=True, exist_ok=True)

        # Section regex patterns
        self.section_patterns = {
            "abstract": r"(?i)^abstract$",
            "introduction": r"(?i)^(1\.?\s*)?introduction$",
            "methods": r"(?i)^(2\.?\s*)?(method|methodology|approach|proposed)",
            "results": r"(?i)^([\d]\.?\s*)?(results?|experiments?|evaluation)",
            "discussion": r"(?i)^([\d]\.?\s*)?discussion",
            "conclusion": r"(?i)^([\d]\.?\s*)?conclusion",
            "limitations": r"(?i)^([\d]\.?\s*)?limitation",
            "references": r"(?i)^references$",
        }

    def download_pdf(self, arxiv_id: str, pdf_url: str) -> Optional[Path]:
        """Downloads PDF from pdf_url to local cache path if not already cached."""
        clean_id = re.sub(r"[^\w\.-]", "_", arxiv_id)
        cache_path = self.pdf_cache / f"{clean_id}.pdf"

        if cache_path.exists() and cache_path.stat().st_size > 1000:
            return cache_path

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ORION-Research-Agent/1.0"
        }
        try:
            url = pdf_url if pdf_url.endswith(".pdf") or "pdf" in pdf_url else f"https://arxiv.org/pdf/{arxiv_id}"
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            with open(cache_path, "wb") as f:
                f.write(response.content)

            return cache_path
        except Exception as e:
            print(f"[Error] Failed to download PDF from {pdf_url}: {e}")
            return None

    def detect_section(self, text: str) -> str:
        """Checks the first line of text block against section regex patterns."""
        if not text:
            return "body"
        first_line = text.strip().split("\n")[0].strip()
        for section_name, pattern in self.section_patterns.items():
            if re.match(pattern, first_line):
                return section_name
        return "body"

    def parse_pdf(self, pdf_path: Path, arxiv_id: str) -> List[Dict[str, Any]]:
        """Extracts text page by page, splits into blocks, detects sections, and filters out references."""
        raw_blocks: List[Dict[str, Any]] = []
        current_section = "body"

        try:
            doc = fitz.open(str(pdf_path))
            for page_idx, page in enumerate(doc):
                page_num = page_idx + 1
                page_text = page.get_text("text")

                blocks = [b.strip() for b in page_text.split("\n\n") if b.strip()]

                for block in blocks:
                    if len(block) < 50:
                        continue

                    detected = self.detect_section(block)
                    if detected != "body":
                        current_section = detected

                    if current_section == "references":
                        continue

                    raw_blocks.append({
                        "text": block,
                        "section": current_section,
                        "page_num": page_num,
                        "arxiv_id": arxiv_id,
                    })
            doc.close()
        except Exception as e:
            print(f"[Error] Failed to parse PDF {pdf_path}: {e}")

        return raw_blocks

    def chunk_and_store(
        self,
        raw_blocks: List[Dict[str, Any]],
        arxiv_id: str,
        workspace_id: int,
        paper_metadata: Dict[str, Any],
    ) -> int:
        """Splits blocks into chunks and adds them into ChromaDB."""
        if not raw_blocks:
            return 0

        all_docs: List[str] = []
        all_metas: List[Dict[str, Any]] = []
        all_ids: List[str] = []

        title = paper_metadata.get("title", "")
        authors = paper_metadata.get("authors", "")
        year = int(paper_metadata.get("year", 0) or 0)

        for block in raw_blocks:
            chunks = self.text_splitter.split_text(block["text"])
            for chunk in chunks:
                if not chunk.strip():
                    continue
                chunk_id = f"{workspace_id}_{arxiv_id}_{uuid.uuid4().hex[:8]}"
                metadata = {
                    "arxiv_id": str(arxiv_id),
                    "workspace_id": int(workspace_id),
                    "section": str(block["section"]),
                    "page_num": int(block["page_num"]),
                    "title": str(title),
                    "authors": str(authors),
                    "year": int(year),
                }
                all_docs.append(chunk)
                all_metas.append(metadata)
                all_ids.append(chunk_id)

        if not all_docs:
            return 0

        embeddings = self.model.encode(all_docs).tolist()

        batch_size = 100
        for i in range(0, len(all_docs), batch_size):
            self.collection.add(
                documents=all_docs[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                metadatas=all_metas[i:i + batch_size],
                ids=all_ids[i:i + batch_size],
            )

        return len(all_docs)

    def ingest_paper(
        self,
        arxiv_id: str,
        pdf_url: str,
        workspace_id: int,
        paper_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Downloads, parses, chunks, and stores paper in ChromaDB."""
        try:
            pdf_path = self.download_pdf(arxiv_id, pdf_url)
            if not pdf_path or not pdf_path.exists():
                return {
                    "success": False,
                    "arxiv_id": arxiv_id,
                    "chunks_stored": 0,
                    "error": f"Failed to download PDF from {pdf_url}",
                }

            raw_blocks = self.parse_pdf(pdf_path, arxiv_id)
            if not raw_blocks:
                return {
                    "success": False,
                    "arxiv_id": arxiv_id,
                    "chunks_stored": 0,
                    "error": "No valid text blocks parsed from PDF",
                }

            chunks_stored = self.chunk_and_store(
                raw_blocks=raw_blocks,
                arxiv_id=arxiv_id,
                workspace_id=workspace_id,
                paper_metadata=paper_metadata,
            )

            return {
                "success": True,
                "arxiv_id": arxiv_id,
                "chunks_stored": chunks_stored,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "arxiv_id": arxiv_id,
                "chunks_stored": 0,
                "error": str(e),
            }

    def query_chunks(
        self,
        question: str,
        workspace_id: int,
        n_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Embeds question and queries ChromaDB for relevant paper chunks in the given workspace."""
        try:
            q_emb = self.model.encode(question).tolist()
            res = self.collection.query(
                query_embeddings=[q_emb],
                n_results=n_results,
                where={"workspace_id": int(workspace_id)},
            )

            output: List[Dict[str, Any]] = []
            if not res or not res.get("documents") or not res["documents"][0]:
                return output

            docs = res["documents"][0]
            metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
            distances = res["distances"][0] if res.get("distances") else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, distances):
                output.append({
                    "text": doc,
                    "arxiv_id": meta.get("arxiv_id", ""),
                    "section": meta.get("section", "body"),
                    "page_num": meta.get("page_num", 1),
                    "title": meta.get("title", ""),
                    "authors": meta.get("authors", ""),
                    "year": meta.get("year", 0),
                    "distance": float(dist),
                })

            return output
        except Exception as e:
            print(f"[Error] query_chunks failed: {e}")
            return []
