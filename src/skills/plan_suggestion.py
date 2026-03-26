"""Skill 3: 需求方案建议 — 基于仓库上下文给出实现方案"""

from __future__ import annotations

import logging
import re

from src.prompts.plan_suggestion import SYSTEM_PROMPT, USER_TEMPLATE
from src.schemas.output import PlanSuggestionOutput
from src.skills.base import BaseSkill
from src.tools.code_search import search_code
from src.tools.file_reader import list_directory, read_key_files

logger = logging.getLogger(__name__)


class PlanSuggestionSkill(BaseSkill):
    name = "plan_suggestion"

    def execute(self, query: str, context: list[str]) -> dict:
        dir_structure = self._get_directory_structure()
        key_files = self._get_key_files()
        related_code = self._search_related_code(query)

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

    def _get_directory_structure(self) -> str:
        return list_directory.invoke({
            "dir_path": self.repo_path,
            "repo_path": self.repo_path,
            "max_depth": 3,
        })

    def _get_key_files(self) -> str:
        return read_key_files.invoke({"repo_path": self.repo_path})

    def _search_related_code(self, query: str) -> str:
        """从需求描述中提取关键词并搜索相关代码。"""
        keywords = _extract_keywords(query)
        if not keywords:
            return "(未提取到搜索关键词)"

        results: list[str] = []
        for kw in keywords[:3]:
            r = search_code.invoke({
                "pattern": kw,
                "repo_path": self.repo_path,
                "max_results": 10,
            })
            if "未找到" not in r:
                results.append(r)

        return "\n\n".join(results) if results else "(未找到相关代码)"


_CJK_WORD_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_EN_WORD_RE = re.compile(r"[A-Z][a-z]+(?:[A-Z][a-z]+)*|[a-zA-Z_]\w{3,}")
_STOP_WORDS = {
    "请", "的", "是", "在", "和", "有", "一个", "这个", "那个", "我们", "需要",
    "功能", "实现", "添加", "修改", "支持", "方案", "建议", "分析",
    "the", "this", "that", "with", "from", "have", "will", "should",
    "need", "want", "please", "implement", "function", "method",
}


def _extract_keywords(text: str) -> list[str]:
    """从自然语言文本中提取可用于代码搜索的关键词。"""
    words: list[str] = []
    for m in _EN_WORD_RE.finditer(text):
        w = m.group()
        if w.lower() not in _STOP_WORDS and len(w) >= 3:
            words.append(w)
    for m in _CJK_WORD_RE.finditer(text):
        w = m.group()
        if w not in _STOP_WORDS:
            words.append(w)
    seen: set[str] = set()
    unique: list[str] = []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique.append(w)
    return unique
