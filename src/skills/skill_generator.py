"""Skill Generator — 运行上游分析 Skill 并生成结构化 Skill 规格"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from src.prompts.skill_generator import (
    MD_SYSTEM_PROMPT,
    MD_USER_TEMPLATE,
    SPEC_SYSTEM_PROMPT,
    SPEC_USER_TEMPLATE,
)
from src.schemas.output import SkillSpecOutput
from src.skills.base import BaseSkill

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class SkillGeneratorSkill(BaseSkill):
    """编排上游分析 Skill，生成结构化 Skill 规格。"""

    name = "skill_generator"

    def execute(self, query: str, context: dict | None) -> dict:
        """运行 repo_background + plan_suggestion + chain_analysis，汇总后生成 SkillSpec。"""
        from src.skills.chain_analysis import ChainAnalysisSkill
        from src.skills.plan_suggestion import PlanSuggestionSkill
        from src.skills.repo_background import RepoBackgroundSkill

        ctx = self._normalize_context(context)
        repo_bg = self._run_sub_skill(RepoBackgroundSkill, query, context)
        plan = self._run_sub_skill(PlanSuggestionSkill, query, context)
        chain_query = self._build_chain_query(query, ctx.combined_context)
        chain = self._run_sub_skill(ChainAnalysisSkill, chain_query, context)

        return {
            "repo_background": repo_bg,
            "plan_suggestion": plan,
            "chain_analysis": chain,
            "chain_query": chain_query,
        }

    def _run_sub_skill(
        self, skill_cls: type[BaseSkill], query: str, context: dict | None
    ) -> dict:
        try:
            skill = skill_cls(llm=self.llm, repo_path=self.repo_path)
            result = skill.execute(query, context)
            logger.info("[skill_generator] %s 完成", skill_cls.name)
            return result
        except Exception as e:
            logger.warning("[skill_generator] %s 失败: %s", skill_cls.name, e)
            return {"error": str(e)}

    def generate_spec(
        self, query: str, analysis_results: dict, context: dict | None
    ) -> dict:
        """基于分析结果生成结构化 Skill 规格。"""
        ctx = self._normalize_context(context)
        repo_bg = analysis_results.get("repo_background", {})
        plan = analysis_results.get("plan_suggestion", {})
        chain = analysis_results.get("chain_analysis", {})

        repo_bg_text = self._format_analysis("仓库背景", repo_bg)
        plan_text = self._format_analysis("需求方案", plan)
        chain_text = self._format_analysis("代码链路", chain)
        context_text = "\n\n".join(ctx.combined_context) if ctx.combined_context else "(无额外上下文)"

        user_message = SPEC_USER_TEMPLATE.format(
            user_query=query,
            repo_path=self.repo_path,
            repo_background=repo_bg_text,
            plan_analysis=plan_text,
            chain_analysis=chain_text,
            retrieved_context=context_text,
        )

        result = self._call_llm_structured(
            system_prompt=SPEC_SYSTEM_PROMPT,
            user_message=user_message,
            output_schema=SkillSpecOutput,
        )
        logger.info("[skill_generator] Spec 生成完成: %s", result.name)
        return result.model_dump()

    def render_markdown(self, spec: dict) -> str:
        """将结构化规格渲染为 SKILL.md 内容（Codex 兼容格式）。

        优先使用 spec 中的 final_markdown（如果它已包含 YAML frontmatter）。
        否则通过 LLM 渲染，并确保输出包含 frontmatter。
        """
        existing_md = spec.get("final_markdown", "")
        if existing_md and len(existing_md) > 200:
            return self._ensure_frontmatter(existing_md, spec)

        user_message = MD_USER_TEMPLATE.format(
            name=spec.get("name", "unnamed-skill"),
            description=spec.get("description", ""),
            use_when=self._list_to_bullets(spec.get("use_when", [])),
            do_not_use_when=self._list_to_bullets(spec.get("do_not_use_when", [])),
            required_inputs=self._list_to_bullets(spec.get("required_inputs", [])),
            background_knowledge=self._list_to_bullets(spec.get("background_knowledge", [])),
            business_glossary=self._list_to_bullets(spec.get("business_glossary", [])),
            scene_entry_points=self._list_to_bullets(spec.get("scene_entry_points", [])),
            typical_call_chains=self._list_to_bullets(spec.get("typical_call_chains", [])),
            workflow_steps=self._list_to_numbered(spec.get("workflow_steps", [])),
            key_paths=self._list_to_bullets(spec.get("key_paths", [])),
            commands=self._list_to_bullets(spec.get("commands", [])),
            validation_checks=self._list_to_bullets(spec.get("validation_checks", [])),
            debug_checklist=self._list_to_bullets(spec.get("debug_checklist", [])),
            search_keywords=self._list_to_bullets(spec.get("search_keywords", [])),
            example_requests=self._list_to_bullets(spec.get("example_requests", [])),
            assumptions=self._list_to_bullets(spec.get("assumptions", [])),
        )

        messages = [
            {"role": "system", "content": MD_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        response = self.llm.invoke(messages)
        return self._ensure_frontmatter(response.content, spec)

    @staticmethod
    def _ensure_frontmatter(markdown: str, spec: dict) -> str:
        """确保 Markdown 以 YAML frontmatter 开头（Codex 要求）。"""
        stripped = markdown.strip()
        if stripped.startswith("---"):
            return stripped

        name = spec.get("name", "unnamed-skill")
        desc = spec.get("description", "").replace('"', '\\"')
        frontmatter = f'---\nname: {name}\ndescription: "{desc}"\n---\n\n'
        return frontmatter + stripped

    @staticmethod
    def _format_analysis(title: str, data: dict) -> str:
        if not data or data.get("error"):
            return f"({title}分析未完成)"
        lines: list[str] = []
        for key, value in data.items():
            if isinstance(value, list):
                items = "\n".join(f"  - {v}" for v in value[:10])
                lines.append(f"- **{key}**:\n{items}")
            elif isinstance(value, str):
                lines.append(f"- **{key}**: {value[:500]}")
            else:
                lines.append(f"- **{key}**: {value}")
        return "\n".join(lines) if lines else f"({title}无数据)"

    @staticmethod
    def _build_chain_query(query: str, context: list[str]) -> str:
        terms = SkillGeneratorSkill._extract_scene_terms(query, context)
        if not terms:
            return (
                "请分析与以下需求最相关的业务调用链，并优先定位候选入口、配置开关和关键分支："
                f"{query}"
            )

        joined = " / ".join(terms[:6])
        return (
            "请分析该业务场景在仓库中的典型调用链，优先找入口方法、活动或价格相关分支、"
            f"配置开关与关键服务。场景词: {joined}。原始需求: {query}"
        )

    @staticmethod
    def _extract_scene_terms(query: str, context: list[str]) -> list[str]:
        candidates: list[str] = []

        for m in re.finditer(r"[A-Z][a-z]+(?:[A-Z][a-z]+)+", query):
            candidates.append(m.group())
        for m in re.finditer(r"[a-zA-Z_]\w{3,}", query):
            word = m.group()
            lowered = word.lower()
            if lowered not in {
                "skill", "prompt", "scene", "generic", "create", "generated",
                "common", "coding", "code", "context", "information",
            }:
                candidates.append(word)
        if not candidates:
            for m in re.finditer(r"[\u4e00-\u9fff]{2,6}", query):
                candidates.append(m.group())

        joined_context = "\n".join(context[:3])
        alias_map = {
            "一分购": ["一分购", "一分钱购", "营销活动", "活动价", "promotion", "activity"],
            "支付": ["支付", "pay", "payment", "下单", "收银台"],
            "退款": ["退款", "refund", "reverse", "售后"],
        }
        for key, aliases in alias_map.items():
            if key in query or key in joined_context:
                candidates.extend(aliases)

        seen: set[str] = set()
        result: list[str] = []
        for item in candidates:
            norm = item.strip()
            if not norm:
                continue
            lowered = norm.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            result.append(norm)
        return result

    @staticmethod
    def _list_to_bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "(无)"

    @staticmethod
    def _list_to_numbered(items: list[str]) -> str:
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items)) if items else "(无)"
