"""Skill 基类 — 定义统一的 Skill 接口"""

from __future__ import annotations

import json
import logging
import re
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
        """调用 LLM 并返回结构化输出。

        兼容 MiniMax 等模型将结果包装在 {ClassName: {fields}} 的情况。
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        logger.info("[%s] 调用 LLM (structured output: %s)", self.name, output_schema.__name__)

        try:
            structured_llm = self.llm.with_structured_output(output_schema)
            result = structured_llm.invoke(messages)
            return result
        except Exception as e:
            logger.warning("[%s] structured output 失败，尝试 fallback: %s", self.name, e)

        schema_json = json.dumps(
            output_schema.model_json_schema(), ensure_ascii=False, indent=None,
        )
        json_system = (
            system_prompt
            + "\n\n【重要】你必须仅返回纯 JSON 对象，不要包含 Markdown、注释或其他格式。"
            "JSON 必须严格符合以下 Schema:\n"
            + schema_json
        )
        json_messages = [
            {"role": "system", "content": json_system},
            {"role": "user", "content": user_message},
        ]

        raw_result = self.llm.invoke(json_messages)
        text = raw_result.content.strip()

        start = text.find("{")
        end = text.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError(f"LLM 返回内容不含有效 JSON: {text[:200]}")

        text = text[start:end]
        data = json.loads(text)

        if output_schema.__name__ in data and isinstance(data[output_schema.__name__], dict):
            data = data[output_schema.__name__]

        normalized_data = _normalize_data_for_schema(data, output_schema)

        try:
            validated = output_schema.model_validate(normalized_data)
            return validated
        except Exception:
            raise


def _coerce_value_by_type(value: object, annotation: object) -> object:
    """按字段类型做轻量归一化。"""
    ann = str(annotation)

    if "list[str]" in ann or "typing.List[str]" in ann:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return []
            parts = re.split(r"\n+|[；;。]+", s)
            cleaned = [p.strip(" -•\t") for p in parts if p.strip(" -•\t")]
            return cleaned if cleaned else [s]
        return [str(value).strip()] if value is not None else []

    if ann == "str" or ann.endswith(".str"):
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(str(v) for v in value if str(v).strip())
        return "" if value is None else str(value)

    return value


def _normalize_data_for_schema(data: dict, output_schema: type[BaseModel]) -> dict:
    """根据 schema 归一化 data。"""
    normalized = dict(data)
    for field_name, field_info in output_schema.model_fields.items():
        if field_name not in normalized:
            continue
        normalized[field_name] = _coerce_value_by_type(
            normalized[field_name], field_info.annotation
        )
    return normalized
