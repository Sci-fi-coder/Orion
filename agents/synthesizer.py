import sys
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Insert parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
from typing import List, Dict, Any, Optional

from config import call_llm
from tools.ingest_tool import IngestTool


class SynthesizerAgent:
    """Retrieves relevant chunks from ChromaDB, classifies stance, grades evidence quality,

    and synthesizes structured answers with inline citations.
    """

    def __init__(self):
        self.ingest = IngestTool()
        self.confidence_threshold: float = 1.2

    def classify_stance(self, chunk_text: str, question: str) -> str:
        """Classifies the stance of a text chunk relative to the question as SUPPORTS, CONTRADICTS, or NEUTRAL."""
        prompt = (
            f"Given this question: {question}\n"
            f"And this text chunk: {chunk_text[:300]}\n"
            "Classify the stance as exactly one of:\n"
            "SUPPORTS, CONTRADICTS, NEUTRAL\n"
            "Reply with only the single word."
        )
        try:
            raw = call_llm(prompt).strip().upper()
            if "SUPPORT" in raw:
                return "SUPPORTS"
            if "CONTRADICT" in raw:
                return "CONTRADICTS"
            if "NEUTRAL" in raw:
                return "NEUTRAL"
            return "NEUTRAL"
        except Exception as e:
            print(f"[Warning] classify_stance failed: {e}")
            return "NEUTRAL"

    def grade_evidence(self, chunk_text: str) -> str:
        """Classifies the evidence grade of a text chunk as EXPERIMENTAL, THEORETICAL, SURVEY, or ASSERTION."""
        prompt = (
            "Classify this text as exactly one of:\n"
            "EXPERIMENTAL (measured results/experiments),\n"
            "THEORETICAL (mathematical proofs/theory),\n"
            "SURVEY (literature review/comparison),\n"
            "ASSERTION (unsupported claim/opinion)\n"
            f"Text: {chunk_text[:300]}\n"
            "Reply with only the single word."
        )
        try:
            raw = call_llm(prompt).strip().upper()
            if "EXPERIMENTAL" in raw:
                return "EXPERIMENTAL"
            if "THEORETICAL" in raw:
                return "THEORETICAL"
            if "SURVEY" in raw:
                return "SURVEY"
            if "ASSERTION" in raw:
                return "ASSERTION"
            return "ASSERTION"
        except Exception as e:
            print(f"[Warning] grade_evidence failed: {e}")
            return "ASSERTION"

    def synthesize(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
        web_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Synthesizes structured research answer using chunk and web contexts with citations."""
        chunk_context_lines = []
        for c in chunks:
            section = c.get("section", "body")
            arxiv_id = c.get("arxiv_id", "arxiv")
            page_num = c.get("page_num", 1)
            text = c.get("text", "")
            chunk_context_lines.append(f"[{section}][{arxiv_id} p.{page_num}]: {text}")

        web_context_lines = []
        for w in web_results:
            title = w.get("title", "WEB")
            summary = w.get("summary", "")
            web_context_lines.append(f"[WEB][{title}]: {summary}")

        combined_context = "\n".join(chunk_context_lines + web_context_lines)

        prompt = (
            "You are a research synthesizer. Answer the question\n"
            "using ONLY the provided sources. Include inline\n"
            "citations as [arxiv_id, p.X] or [WEB: title].\n\n"
            f"Question: {question}\n\n"
            "Sources:\n"
            f"{combined_context}\n\n"
            "Provide a structured answer with:\n"
            "1. Direct answer (2-3 sentences)\n"
            "2. Key findings from sources\n"
            "3. Any conflicting evidence noted\n\n"
            "Use citations throughout."
        )

        try:
            response = call_llm(prompt)
        except Exception as e:
            print(f"[Warning] synthesize LLM call failed: {e}")
            response = "Error generating synthesis from sources."

        return {
            "answer": response,
            "chunks_used": len(chunks),
            "web_sources_used": len(web_results),
        }

    def run(
        self,
        question: str,
        workspace_id: int,
        web_results: List[Dict[str, Any]],
        devil_advocate: bool = False,
    ) -> Dict[str, Any]:
        """Main entry point. Queries ChromaDB, checks confidence gate, classifies stance and evidence,

        synthesizes answer, and optionally runs Devil's Advocate critique.
        """
        # 1. Query ChromaDB for relevant chunks
        chunks = self.ingest.query_chunks(
            question=question,
            workspace_id=workspace_id,
            n_results=10,
        )

        # 2. CONFIDENCE GATE
        if not chunks or min(c.get("distance", 2.0) for c in chunks) > self.confidence_threshold:
            return {
                "answer": "Insufficient context. Add more papers.",
                "confidence": 0.0,
                "stance_summary": {},
                "evidence_grades": {},
                "devil_advocate": None,
                "synthesizer_done": True,
                "refused": True,
            }

        # 3. Classify stance and grade evidence for each chunk
        stance_summary = {"SUPPORTS": 0, "CONTRADICTS": 0, "NEUTRAL": 0}
        evidence_grades = {
            "EXPERIMENTAL": 0,
            "THEORETICAL": 0,
            "SURVEY": 0,
            "ASSERTION": 0,
        }

        for chunk in chunks:
            chunk_text = chunk.get("text", "")
            stance = self.classify_stance(chunk_text, question)
            if stance in stance_summary:
                stance_summary[stance] += 1
            else:
                stance_summary["NEUTRAL"] += 1

            grade = self.grade_evidence(chunk_text)
            if grade in evidence_grades:
                evidence_grades[grade] += 1
            else:
                evidence_grades["ASSERTION"] += 1

        # 4. Synthesize structured answer
        synth_res = self.synthesize(question, chunks, web_results)
        synthesized_answer = synth_res.get("answer", "")

        # 5. Compute confidence score as average of (1 - distance/2) for all chunks
        confidences = [max(0.0, min(1.0, 1.0 - (c.get("distance", 0.0) / 2.0))) for c in chunks]
        confidence = float(sum(confidences) / len(confidences)) if confidences else 0.0

        # 6. Devil's Advocate mode (optional)
        devil_advocate_response: Optional[str] = None
        if devil_advocate:
            da_prompt = (
                "You are a critical reviewer. Given this answer:\n"
                f"{synthesized_answer}\n\n"
                "Generate 2-3 critical challenges:\n"
                "- Methodological limitations of supporting evidence\n"
                "- What dissenting research argues\n"
                "- Key assumptions that might not hold\n\n"
                "Be specific and evidence-based."
            )
            try:
                devil_advocate_response = call_llm(da_prompt)
            except Exception as e:
                print(f"[Warning] Devil's advocate call failed: {e}")
                devil_advocate_response = None

        return {
            "answer": synthesized_answer,
            "confidence": confidence,
            "stance_summary": stance_summary,
            "evidence_grades": evidence_grades,
            "devil_advocate": devil_advocate_response,
            "chunks_used": len(chunks),
            "web_sources_used": len(web_results),
            "synthesizer_done": True,
            "refused": False,
        }
