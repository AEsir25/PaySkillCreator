"""LangGraph Agent State 定义"""

from __future__ import annotations

from typing import Literal, TypedDict


SkillType = Literal["repo_background", "chain_analysis", "plan_suggestion"]

VALID_SKILLS: set[str] = {"repo_background", "chain_analysis", "plan_suggestion"}


class AgentState(TypedDict, total=False):
    # --- 输入 ---
    repo_path: str
    user_query: str
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

    # --- 错误信息 ---
    error: str | None

    # --- 元信息（路由原因、耗时、模型等） ---
    metadata: dict
