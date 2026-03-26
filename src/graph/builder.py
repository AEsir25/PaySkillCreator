"""LangGraph StateGraph 构建与编排

工作流:
  skill_router → context_retriever → skill_executor → formatter → (human_review?) → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.graph.nodes import (
    context_retriever,
    formatter,
    human_review,
    skill_executor,
    skill_router,
)
from src.state import AgentState


def _should_review(state: AgentState) -> str:
    """条件边: 判断是否需要人工审核。"""
    if state.get("need_review"):
        return "human_review"
    return END


def build_graph() -> StateGraph:
    """构建并编译 PaySkillCreator 的 StateGraph。"""
    graph = StateGraph(AgentState)

    graph.add_node("skill_router", skill_router)
    graph.add_node("context_retriever", context_retriever)
    graph.add_node("skill_executor", skill_executor)
    graph.add_node("formatter", formatter)
    graph.add_node("human_review", human_review)

    graph.set_entry_point("skill_router")
    graph.add_edge("skill_router", "context_retriever")
    graph.add_edge("context_retriever", "skill_executor")
    graph.add_edge("skill_executor", "formatter")

    graph.add_conditional_edges("formatter", _should_review, {
        "human_review": "human_review",
        END: END,
    })
    graph.add_edge("human_review", END)

    return graph.compile()
