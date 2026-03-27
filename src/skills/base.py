"""Skill 基类 — 定义统一的 Skill 接口"""

from __future__ import annotations

import json
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
        """调用 LLM 并返回结构化输出。

        兼容 MiniMax 等模型将结果包装在 {ClassName: {fields}} 的情况。
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        logger.info("[%s] 调用 LLM (structured output: %s)", self.name, output_schema.__name__)

        # #region agent log
        import time as _time
        _log_path = "/Users/zhengyehui.1/PaySkillCreator/.cursor/debug-1cdcab.log"
        # #endregion

        try:
            structured_llm = self.llm.with_structured_output(output_schema)
            result = structured_llm.invoke(messages)
            # #region agent log
            with open(_log_path, "a") as _f: _f.write(json.dumps({"sessionId":"1cdcab","location":"base.py:_call_llm_structured","message":"structured ok","data":{"schema":output_schema.__name__,"result_type":type(result).__name__},"hypothesisId":"verify","timestamp":int(_time.time()*1000)}) + "\n")
            # #endregion
            return result
        except Exception as e:
            logger.warning("[%s] structured output 失败，尝试 fallback: %s", self.name, e)
            # #region agent log
            with open(_log_path, "a") as _f: _f.write(json.dumps({"sessionId":"1cdcab","location":"base.py:_call_llm_structured","message":"structured failed, trying fallback","data":{"schema":output_schema.__name__,"error":str(e)[:200]},"hypothesisId":"verify","timestamp":int(_time.time()*1000)}) + "\n")
            # #endregion

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

        # #region agent log
        with open(_log_path, "a") as _f: _f.write(json.dumps({"sessionId":"1cdcab","location":"base.py:_call_llm_structured","message":"fallback raw response","data":{"schema":output_schema.__name__,"content_len":len(text),"content_head":text[:300]},"hypothesisId":"verify","timestamp":int(_time.time()*1000)}) + "\n")
        # #endregion

        start = text.find("{")
        end = text.rfind("}") + 1
        if start < 0 or end <= start:
            raise ValueError(f"LLM 返回内容不含有效 JSON: {text[:200]}")

        text = text[start:end]
        data = json.loads(text)

        if output_schema.__name__ in data and isinstance(data[output_schema.__name__], dict):
            data = data[output_schema.__name__]

        # #region agent log
        with open(_log_path, "a") as _f: _f.write(json.dumps({"sessionId":"1cdcab","location":"base.py:_call_llm_structured","message":"fallback parsed","data":{"schema":output_schema.__name__,"keys":list(data.keys())[:10]},"hypothesisId":"verify","timestamp":int(_time.time()*1000)}) + "\n")
        # #endregion

        return output_schema.model_validate(data)
