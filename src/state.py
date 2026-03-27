"""LangGraph Agent State 定义"""

from __future__ import annotations

from typing import Literal, TypedDict


SkillType = Literal[
    "repo_background", "chain_analysis", "plan_suggestion", "generate_skill"
]

VALID_SKILLS: set[str] = {
    "repo_background", "chain_analysis", "plan_suggestion", "generate_skill",
}

ANALYSIS_SKILLS: set[str] = {"repo_background", "chain_analysis", "plan_suggestion"}


class AgentState(TypedDict, total=False):
    # --- 输入 ---
    repo_path: str
    user_query: str
    requested_skill: str | None
    model_id: str | None

    # --- 路由结果 ---
    skill_type: SkillType

    # --- 检索到的仓库上下文 ---
    retrieved_context: list[str]

    # --- Skill 执行结果（单 skill 分析） ---
    skill_result: dict

    # --- generate_skill 流程: 多 skill 分析结果汇总 ---
    analysis_results: dict

    # --- generate_skill 流程: 结构化 skill 规格 ---
    skill_spec: dict

    # --- 格式化输出 ---
    formatted_output: str

    # --- 人工审核 ---
    need_review: bool
    review_approved: bool | None

    # --- 错误信息 ---
    error: str | None

    # --- 元信息（路由原因、耗时、模型等） ---
    metadata: dict
