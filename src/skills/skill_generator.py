"""Skill Generator — 运行上游分析 Skill 并生成结构化 Skill 规格"""

from __future__ import annotations

import logging
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

    def execute(self, query: str, context: list[str]) -> dict:
        """运行 repo_background + plan_suggestion，汇总后生成 SkillSpec。"""
        from src.skills.plan_suggestion import PlanSuggestionSkill
        from src.skills.repo_background import RepoBackgroundSkill

        repo_bg = self._run_sub_skill(RepoBackgroundSkill, query, context)
        plan = self._run_sub_skill(PlanSuggestionSkill, query, context)

        return {
            "repo_background": repo_bg,
            "plan_suggestion": plan,
        }

    def _run_sub_skill(
        self, skill_cls: type[BaseSkill], query: str, context: list[str]
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
        self, query: str, analysis_results: dict, context: list[str]
    ) -> dict:
        """基于分析结果生成结构化 Skill 规格。"""
        repo_bg = analysis_results.get("repo_background", {})
        plan = analysis_results.get("plan_suggestion", {})

        repo_bg_text = self._format_analysis("仓库背景", repo_bg)
        plan_text = self._format_analysis("需求方案", plan)
        context_text = "\n\n".join(context) if context else "(无额外上下文)"

        user_message = SPEC_USER_TEMPLATE.format(
            user_query=query,
            repo_path=self.repo_path,
            repo_background=repo_bg_text,
            plan_analysis=plan_text,
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
            workflow_steps=self._list_to_numbered(spec.get("workflow_steps", [])),
            key_paths=self._list_to_bullets(spec.get("key_paths", [])),
            commands=self._list_to_bullets(spec.get("commands", [])),
            validation_checks=self._list_to_bullets(spec.get("validation_checks", [])),
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
    def _list_to_bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "(无)"

    @staticmethod
    def _list_to_numbered(items: list[str]) -> str:
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items)) if items else "(无)"
