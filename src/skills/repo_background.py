"""Skill 1: 仓库背景知识 — 基于目录结构和关键文件分析仓库概况"""

from __future__ import annotations

import logging

from src.prompts.repo_background import SYSTEM_PROMPT, USER_TEMPLATE
from src.schemas.output import RepoBackgroundOutput
from src.skills.base import BaseSkill
from src.tools.file_reader import list_directory, read_key_files

logger = logging.getLogger(__name__)


class RepoBackgroundSkill(BaseSkill):
    name = "repo_background"

    def execute(self, query: str, context: list[str]) -> dict:
        dir_structure = self._get_directory_structure()
        key_files = self._get_key_files()

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

    def _get_directory_structure(self) -> str:
        """获取仓库目录结构。优先使用预检索上下文。"""
        return list_directory.invoke({
            "dir_path": self.repo_path,
            "repo_path": self.repo_path,
            "max_depth": 3,
        })

    def _get_key_files(self) -> str:
        """获取关键文件内容。"""
        return read_key_files.invoke({"repo_path": self.repo_path})
