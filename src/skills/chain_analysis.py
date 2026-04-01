"""Skill 2: 代码逻辑链路分析 — 使用 ReAct Agent 多轮追踪调用链"""

from __future__ import annotations

import logging
from functools import partial

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from src.prompts.chain_analysis import FINAL_SUMMARY_PROMPT, SYSTEM_PROMPT
from src.schemas.output import ChainAnalysisOutput
from src.skills.base import BaseSkill
from src.tools.code_search import search_code, search_references, search_symbol
from src.tools.file_reader import read_file
from src.tools.tree_parser import extract_method_body, find_method_calls, parse_file_structure

logger = logging.getLogger(__name__)

MAX_REACT_STEPS = 30


class ChainAnalysisSkill(BaseSkill):
    name = "chain_analysis"

    def execute(self, query: str, context: dict | None) -> dict:
        ctx = self._normalize_context(context)
        analysis_trace = self._run_react_agent(query, ctx)
        result = self._summarize_to_structured(query, analysis_trace)
        logger.info(
            "[chain_analysis] 分析完成: 入口=%s, 调用链长度=%d",
            result.entry_point,
            len(result.call_chain),
        )
        return result.model_dump()

    def _run_react_agent(self, query: str, context: object) -> str:
        """运行 ReAct Agent 进行多轮代码追踪，返回分析过程文本。"""
        tools = self._build_tools()
        system_prompt = SYSTEM_PROMPT.format(repo_path=self.repo_path)

        agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt,
            name="chain_analysis_agent",
        )

        logger.info("[chain_analysis] 启动 ReAct Agent, query=%s", query[:100])

        result = agent.invoke(
            {"messages": [HumanMessage(content=self._build_user_message(query, context))]},
            config={"recursion_limit": MAX_REACT_STEPS},
        )

        messages = result.get("messages", [])
        trace_parts: list[str] = []
        for msg in messages:
            role = msg.__class__.__name__
            content = getattr(msg, "content", "")
            if content and isinstance(content, str):
                trace_parts.append(f"[{role}] {content[:2000]}")

        trace = "\n\n".join(trace_parts)
        logger.info("[chain_analysis] ReAct 完成, %d 条消息, trace 长度=%d", len(messages), len(trace))
        return trace

    def _build_user_message(self, query: str, context: object) -> str:
        ctx = self._normalize_context(context)
        hints = ctx.keyword_search_hits[:2] + ctx.semantic_search_hits[:1]
        hint_block = ""
        if hints:
            hint_block = "\n\n已检索到的候选线索，请优先从这些结果涉及的文件开始追踪：\n\n" + "\n\n".join(hints)

        return (
            f"请分析以下代码的调用链路:\n\n{query}\n\n"
            f"仓库路径: {self.repo_path}\n"
            f"请使用工具逐步追踪调用链路，追踪深度 3-5 层。"
            f"{hint_block}"
        )

    def _build_tools(self) -> list:
        """构建 Agent 可用的工具列表。"""
        return [
            search_code,
            search_symbol,
            search_references,
            read_file,
            extract_method_body,
            find_method_calls,
            parse_file_structure,
        ]

    def _summarize_to_structured(self, query: str, trace: str) -> ChainAnalysisOutput:
        """将 ReAct 分析过程总结为结构化输出。"""
        max_trace_len = 12000
        if len(trace) > max_trace_len:
            trace = trace[:max_trace_len] + "\n... (分析过程过长，已截断)"

        user_message = FINAL_SUMMARY_PROMPT.format(
            query=query,
            analysis_trace=trace,
        )

        return self._call_llm_structured(
            system_prompt="你是一个代码分析结果整理专家。请根据分析过程记录，生成结构化的链路分析结果。",
            user_message=user_message,
            output_schema=ChainAnalysisOutput,
        )
