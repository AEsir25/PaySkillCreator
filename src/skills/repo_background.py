"""Skill 1: 仓库背景知识 — 基于目录结构和关键文件分析仓库概况"""

from __future__ import annotations

import logging

from src.prompts.repo_background import SYSTEM_PROMPT, USER_TEMPLATE
from src.schemas.output import RepoBackgroundOutput
from src.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class RepoBackgroundSkill(BaseSkill):
    name = "repo_background"

    def execute(self, query: str, context: dict | None) -> dict:
        ctx = self._normalize_context(context)
        dir_structure = ctx.directory_structure
        key_files = ctx.key_files_content

        user_message = USER_TEMPLATE.format(
            query=query,
            directory_structure=dir_structure,
            key_files_content=key_files,
        )

        result = self._call_llm_structured(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            output_schema=RepoBackgroundOutput,
        )

        logger.info("[repo_background] 分析完成: %d 个模块", len(result.core_modules))
        return result.model_dump()
