import sys
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Insert parent directory to sys.path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
from config import call_llm


SYSTEM_PROMPT = """You are a research coordinator. Given a research topic, decompose it into 3-5 focused sub-questions that together cover the topic comprehensively. Also classify the topic complexity.

Respond ONLY with valid JSON in this exact format:
{
  "main_topic": "the original topic",
  "complexity": "simple" or "moderate" or "complex",
  "sub_questions": [
    "sub-question 1",
    "sub-question 2",
    "sub-question 3"
  ],
  "search_strategy": "arxiv_only" or "web_only" or "hybrid",
  "reasoning": "brief explanation of decomposition"
}

Rules:
- simple: factual, single concept -> 2-3 sub_questions, web_only
- moderate: comparative or explanatory -> 3-4 sub_questions, hybrid
- complex: cutting-edge, multi-concept, research-level -> 4-5 sub_questions, hybrid
- search_strategy hybrid means search both arxiv and web"""


class CoordinatorAgent:
    """Stateless agent that decomposes a research topic into a structured plan."""

    def decompose(self, topic: str) -> dict:
        """
        Calls LLM with a research decomposition prompt and returns a structured plan dict.
        Falls back to a safe default if JSON parsing fails.
        """
        prompt = f"{SYSTEM_PROMPT}\n\nResearch topic: {topic}"

        fallback = {
            "main_topic": topic,
            "complexity": "moderate",
            "sub_questions": [topic],
            "search_strategy": "hybrid",
            "reasoning": "fallback plan",
        }

        try:
            raw = call_llm(prompt)

            # Strip markdown fences if present (```json ... ``` or ``` ... ```)
            cleaned = raw.strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE)
            cleaned = cleaned.strip()

            # Find JSON object in response even if there's extra text around it
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            plan = json.loads(cleaned)

            # Validate required fields and types
            if not isinstance(plan.get("sub_questions"), list):
                plan["sub_questions"] = [topic]
            if plan.get("complexity") not in ("simple", "moderate", "complex"):
                plan["complexity"] = "moderate"
            if plan.get("search_strategy") not in ("arxiv_only", "web_only", "hybrid"):
                plan["search_strategy"] = "hybrid"
            if "main_topic" not in plan:
                plan["main_topic"] = topic
            if "reasoning" not in plan:
                plan["reasoning"] = ""

            return plan

        except Exception as e:
            print(f"[Warning] CoordinatorAgent.decompose failed to parse JSON ({e}), using fallback.")
            return fallback

    def run(self, topic: str) -> dict:
        """Main entry point. Decomposes topic and marks coordinator as done."""
        plan = self.decompose(topic)
        plan["coordinator_done"] = True
        return plan
