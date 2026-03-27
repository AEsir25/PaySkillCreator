"""LangGraph StateGraph 构建与编排

工作流 (分析模式):
  skill_router → context_retriever → skill_executor → formatter → (human_review?) → END

工作流 (SKILL.md 生成模式):
  skill_router → context_retriever → skill_executor → skill_spec_generator
  → skill_md_formatter → (human_review?) → END
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.graph.nodes import (
    context_retriever,
    formatter,
    human_review,
    skill_executor,
    skill_md_formatter,
    skill_router,
    skill_spec_generator,
)
from src.state import AgentState


def _should_review(state: AgentState) -> str:
    """条件边: 判断是否需要人工审核。"""
    if state.get("need_review"):
        return "human_review"
    return END


def _after_executor(state: AgentState) -> str:
    """条件边: skill_executor 之后根据 skill_type 选择分支。

    - generate_skill → skill_spec_generator (进入 SKILL.md 生成流程)
    - 其他 → formatter (原有分析格式化)
    """
    if state.get("skill_type") == "generate_skill":
        return "skill_spec_generator"
    return "formatter"


def build_graph(checkpointer: bool = True) -> StateGraph:
    """构建并编译 PaySkillCreator 的 StateGraph。

    Args:
        checkpointer: 是否启用 MemorySaver（human_review 的 interrupt 需要）
    """
    graph = StateGraph(AgentState)

    graph.add_node("skill_router", skill_router)
    graph.add_node("context_retriever", context_retriever)
    graph.add_node("skill_executor", skill_executor)
    graph.add_node("formatter", formatter)
    graph.add_node("skill_spec_generator", skill_spec_generator)
    graph.add_node("skill_md_formatter", skill_md_formatter)
    graph.add_node("human_review", human_review)

    graph.set_entry_point("skill_router")
    graph.add_edge("skill_router", "context_retriever")
    graph.add_edge("context_retriever", "skill_executor")

    graph.add_conditional_edges("skill_executor", _after_executor, {
        "formatter": "formatter",
        "skill_spec_generator": "skill_spec_generator",
    })

    graph.add_edge("skill_spec_generator", "skill_md_formatter")

    graph.add_conditional_edges("formatter", _should_review, {
        "human_review": "human_review",
        END: END,
    })
    graph.add_conditional_edges("skill_md_formatter", _should_review, {
        "human_review": "human_review",
        END: END,
    })
    graph.add_edge("human_review", END)

    memory = MemorySaver() if checkpointer else None
    return graph.compile(checkpointer=memory)
