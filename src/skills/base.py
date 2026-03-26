"""Skill 基类 — 定义统一的 Skill 接口"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class BaseSkill(ABC):
    """所有 Skill 的基类。"""

    name: str = "base"

    def __init__(self, llm: ChatOpenAI, repo_path: str) -> None:
        self.llm = llm
        self.repo_path = repo_path

    @abstractmethod
    def execute(self, query: str, context: list[str]) -> dict:
        """执行 Skill 分析。

        Args:
            query: 用户问题
            context: 预检索的仓库上下文列表

        Returns:
            与对应 Pydantic Output Schema 字段一致的 dict
        """
        ...

    def _call_llm_structured(
        self,
        system_prompt: str,
        user_message: str,
        output_schema: type[BaseModel],
    ) -> BaseModel:
        """调用 LLM 并返回结构化输出。"""
        structured_llm = self.llm.with_structured_output(output_schema)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        logger.info("[%s] 调用 LLM (structured output: %s)", self.name, output_schema.__name__)
        return structured_llm.invoke(messages)
