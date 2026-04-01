"""Skill 3: 需求方案建议 — 基于仓库上下文给出实现方案"""

from __future__ import annotations

import logging
from src.prompts.plan_suggestion import SYSTEM_PROMPT, USER_TEMPLATE
from src.schemas.output import PlanSuggestionOutput
from src.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class PlanSuggestionSkill(BaseSkill):
    name = "plan_suggestion"

    def execute(self, query: str, context: dict | None) -> dict:
        ctx = self._normalize_context(context)
        dir_structure = ctx.directory_structure
        key_files = ctx.key_files_content
        related_parts = ctx.keyword_search_hits + ctx.semantic_search_hits
        related_code = "\n\n".join(related_parts) if related_parts else "(未找到相关代码)"

        user_message = USER_TEMPLATE.format(
            query=query,
            directory_structure=dir_structure,
            key_files_content=key_files,
            related_code=related_code,
        )

        result = self._call_llm_structured(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            output_schema=PlanSuggestionOutput,
        )

        logger.info(
            "[plan_suggestion] 分析完成: %d 个改动点",
            len(result.candidate_changes),
        )
        return result.model_dump()
