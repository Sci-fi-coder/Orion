import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class CriticAgent:
    """Evaluates synthesis output using deterministic quality gates without LLM calls."""

    def run(
        self,
        question: str,
        synthesis_output: dict,
        replan_count: int = 0,
        max_replans: int = 2,
    ) -> dict:
        """Rule-based only, no LLM calls.

        Evaluates refused state, replan count, confidence score, and answer length.
        Always includes: {accepted, needs_replan, feedback, replan_count, critic_done: True}
        """
        refused = synthesis_output.get("refused", False)
        confidence = synthesis_output.get("confidence", 0.0)
        answer = synthesis_output.get("answer", "") or ""

        if refused:
            return {
                "accepted": False,
                "needs_replan": True,
                "feedback": "No context found",
                "replan_count": replan_count,
                "critic_done": True,
            }

        if replan_count >= max_replans:
            return {
                "accepted": True,
                "needs_replan": False,
                "feedback": "Max replans reached",
                "replan_count": replan_count,
                "critic_done": True,
            }

        if confidence < 0.3:
            return {
                "accepted": False,
                "needs_replan": True,
                "feedback": "Low confidence",
                "replan_count": replan_count,
                "critic_done": True,
            }

        if len(answer) < 100:
            return {
                "accepted": False,
                "needs_replan": True,
                "feedback": "Answer too short",
                "replan_count": replan_count,
                "critic_done": True,
            }

        return {
            "accepted": True,
            "needs_replan": False,
            "feedback": "Answer meets quality bar",
            "replan_count": replan_count,
            "critic_done": True,
        }
