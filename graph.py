import os
import sys
from typing import TypedDict, List

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
try:
    import sentence_transformers
except Exception:
    pass

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph.graph import StateGraph, END
from agents.coordinator import CoordinatorAgent
from agents.researcher import ResearcherAgent
from agents.synthesizer import SynthesizerAgent
from agents.critic import CriticAgent


class OrionState(TypedDict):
    topic: str
    workspace_id: int
    plan: dict
    research_results: dict
    synthesis_output: dict
    critic_result: dict
    final_answer: str
    replan_count: int
    devil_advocate: bool
    reasoning_log: List[str]


def coordinator_node(state: OrionState) -> dict:
    coordinator = CoordinatorAgent()
    plan = coordinator.run(state["topic"])
    sub_count = len(plan.get("sub_questions", []))
    strategy = plan.get("search_strategy", "hybrid")
    log_entry = f"Coordinator generated {sub_count} sub-questions with strategy '{strategy}'."
    return {
        "plan": plan,
        "reasoning_log": state.get("reasoning_log", []) + [log_entry],
    }


def researcher_node(state: OrionState) -> dict:
    researcher = ResearcherAgent()
    results = researcher.run(state["plan"], state["workspace_id"])
    arxiv_count = results.get("total_found", len(results.get("arxiv_results", [])))
    web_count = len(results.get("web_results", []))
    ingested_count = len(results.get("ingested_papers", []))
    log_entry = f"Researcher retrieved {arxiv_count} ArXiv papers and {web_count} web results ({ingested_count} newly ingested)."
    return {
        "research_results": results,
        "reasoning_log": state.get("reasoning_log", []) + [log_entry],
    }


def synthesizer_node(state: OrionState) -> dict:
    synthesizer = SynthesizerAgent()
    web_results = state.get("research_results", {}).get("web_results", [])
    output = synthesizer.run(
        question=state["topic"],
        workspace_id=state["workspace_id"],
        web_results=web_results,
        devil_advocate=state.get("devil_advocate", False),
    )
    conf = output.get("confidence", 0.0)
    refused = output.get("refused", False)
    log_entry = f"Synthesizer completed synthesis (confidence={conf:.2f}, refused={refused})."
    return {
        "synthesis_output": output,
        "reasoning_log": state.get("reasoning_log", []) + [log_entry],
    }


def critic_node(state: OrionState) -> dict:
    critic = CriticAgent()
    crit_result = critic.run(
        question=state["topic"],
        synthesis_output=state.get("synthesis_output", {}),
        replan_count=state.get("replan_count", 0),
    )
    accepted = crit_result.get("accepted", False)
    feedback = crit_result.get("feedback", "")
    log_entry = f"Critic evaluated output: accepted={accepted}, feedback='{feedback}'."
    
    updates = {
        "critic_result": crit_result,
        "reasoning_log": state.get("reasoning_log", []) + [log_entry],
    }
    if accepted:
        updates["final_answer"] = state.get("synthesis_output", {}).get("answer", "")
    else:
        # Fallback to synthesis answer if not accepted
        updates["final_answer"] = state.get("synthesis_output", {}).get("answer", "")

    return updates


def route_after_critic(state: OrionState) -> str:
    critic_res = state.get("critic_result", {})
    if critic_res.get("accepted"):
        return "END"
    if state.get("replan_count", 0) >= 2:
        return "END"
    state["replan_count"] = state.get("replan_count", 0) + 1
    return "researcher"


# Construct graph
builder = StateGraph(OrionState)
builder.add_node("coordinator", coordinator_node)
builder.add_node("researcher", researcher_node)
builder.add_node("synthesizer", synthesizer_node)
builder.add_node("critic", critic_node)

builder.set_entry_point("coordinator")
builder.add_edge("coordinator", "researcher")
builder.add_edge("researcher", "synthesizer")
builder.add_edge("synthesizer", "critic")

builder.add_conditional_edges(
    "critic",
    route_after_critic,
    {
        "END": END,
        END: END,
        "researcher": "researcher",
    },
)

app = builder.compile()


def run_orion(
    topic: str,
    workspace_id: int = 1,
    devil_advocate: bool = False,
) -> dict:
    initial_state: OrionState = {
        "topic": topic,
        "workspace_id": workspace_id,
        "plan": {},
        "research_results": {},
        "synthesis_output": {},
        "critic_result": {},
        "final_answer": "",
        "replan_count": 0,
        "devil_advocate": devil_advocate,
        "reasoning_log": [],
    }
    result = app.invoke(initial_state)
    return result
