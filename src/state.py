"""LangGraph Agent State 定义"""

from __future__ import annotations

from typing import Literal, TypedDict


SkillType = Literal["repo_background", "chain_analysis", "plan_suggestion"]


class AgentState(TypedDict, total=False):
    # --- 输入 ---
    repo_path: str
    user_query: str
    # 用户直接指定的 Skill（可选，为空则自动路由）
    requested_skill: str | None

    # --- 路由结果 ---
    skill_type: SkillType

    # --- 检索到的仓库上下文 ---
    retrieved_context: list[str]

    # --- Skill 执行结果 ---
    skill_result: dict

    # --- 格式化输出 ---
    formatted_output: str

    # --- 人工审核 ---
    need_review: bool
    review_approved: bool | None
