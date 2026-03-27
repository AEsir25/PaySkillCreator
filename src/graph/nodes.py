"""LangGraph 各节点函数实现

每个节点接收 AgentState，返回要更新的字段 dict。
"""

from __future__ import annotations

import json
import logging
import time

import tiktoken
from langgraph.types import interrupt

from src.state import ANALYSIS_SKILLS, VALID_SKILLS, AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token 估算
# ---------------------------------------------------------------------------

_ENCODING: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    global _ENCODING
    if _ENCODING is None:
        try:
            _ENCODING = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def _estimate_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def _truncate_context(parts: list[str], max_tokens: int) -> list[str]:
    """按顺序保留上下文，超过 max_tokens 时截断。"""
    result: list[str] = []
    used = 0
    for part in parts:
        tokens = _estimate_tokens(part)
        if used + tokens > max_tokens:
            remaining = max_tokens - used
            if remaining > 200:
                enc = _get_encoding()
                encoded = enc.encode(part)[:remaining]
                result.append(enc.decode(encoded) + "\n... (上下文已截断)")
            break
        result.append(part)
        used += tokens
    return result


# ---------------------------------------------------------------------------
# Node 1: Skill 路由
# ---------------------------------------------------------------------------

def skill_router(state: AgentState) -> dict:
    """根据用户输入确定要使用的 Skill 类型。

    优先级: 用户指定 > LLM 意图识别 > 关键词 fallback
    """
    requested = state.get("requested_skill")
    metadata = dict(state.get("metadata", {}))

    if requested and requested in VALID_SKILLS:
        logger.info("使用用户指定的 Skill: %s", requested)
        metadata["router_method"] = "user_specified"
        metadata["router_reason"] = f"用户通过 --skill 指定: {requested}"
        return {"skill_type": requested, "metadata": metadata}

    query = state.get("user_query", "")

    skill, reason = _llm_route(query)
    if skill:
        logger.info("LLM 路由: %s (原因: %s)", skill, reason)
        metadata["router_method"] = "llm"
        metadata["router_reason"] = reason
        return {"skill_type": skill, "metadata": metadata}

    skill = _keyword_route(query)
    logger.info("关键词 fallback 路由: %s", skill)
    metadata["router_method"] = "keyword_fallback"
    metadata["router_reason"] = f"LLM 路由失败，关键词匹配: {skill}"
    return {"skill_type": skill, "metadata": metadata}


def _llm_route(query: str) -> tuple[str | None, str]:
    """使用 LLM 做意图识别。失败时返回 (None, error_msg)。"""
    from src.config import get_llm
    from src.prompts.router import SYSTEM_PROMPT, USER_TEMPLATE, RouterOutput

    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(RouterOutput)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(query=query)},
        ]
        result: RouterOutput = structured_llm.invoke(messages)
        if result.skill_type in VALID_SKILLS:
            return result.skill_type, result.reason
        return None, f"LLM 返回了无效的 skill_type: {result.skill_type}"
    except Exception as e:
        logger.warning("LLM 路由失败，降级为关键词路由: %s", e)
        return None, str(e)


def _keyword_route(query: str) -> str:
    """基于关键词的 fallback 路由。"""
    q = query.lower()
    if any(kw in q for kw in ("skill.md", "skill 文件", "生成 skill", "generate skill", "沉淀为 skill", "创建 skill")):
        return "generate_skill"
    if any(kw in q for kw in ("链路", "调用", "流程", "chain", "trace", "调用链")):
        return "chain_analysis"
    if any(kw in q for kw in ("需求", "方案", "实现", "plan", "设计")):
        return "plan_suggestion"
    return "repo_background"


# ---------------------------------------------------------------------------
# Node 2: 仓库上下文检索
# ---------------------------------------------------------------------------

def context_retriever(state: AgentState) -> dict:
    """根据 skill_type 预检索相关仓库上下文，控制总 token 量。"""
    from src.config import get_settings
    from src.tools.code_search import search_code
    from src.tools.file_reader import list_directory, read_key_files
    from src.tools.vector_search import semantic_search

    skill_type = state.get("skill_type", "repo_background")
    repo_path = state.get("repo_path", "")
    query = state.get("user_query", "")
    settings = get_settings()
    max_tokens = settings.max_context_tokens

    logger.info("检索上下文: skill=%s, repo=%s, max_tokens=%d", skill_type, repo_path, max_tokens)

    parts: list[str] = []

    if skill_type == "repo_background":
        parts.append(list_directory.invoke({
            "dir_path": repo_path, "repo_path": repo_path, "max_depth": 3,
        }))
        parts.append(read_key_files.invoke({"repo_path": repo_path}))

    elif skill_type == "chain_analysis":
        parts.append(list_directory.invoke({
            "dir_path": repo_path, "repo_path": repo_path, "max_depth": 2,
        }))
        keywords = _extract_search_terms(query)
        for kw in keywords[:2]:
            r = search_code.invoke({
                "pattern": kw, "repo_path": repo_path, "max_results": 10,
            })
            if "未找到" not in r:
                parts.append(r)
        try:
            sem = semantic_search.invoke({
                "query": query, "repo_path": repo_path, "top_k": 3,
            })
            if "未找到" not in sem:
                parts.append(sem)
        except Exception as e:
            logger.warning("语义搜索失败，跳过: %s", e)

    elif skill_type == "plan_suggestion":
        parts.append(list_directory.invoke({
            "dir_path": repo_path, "repo_path": repo_path, "max_depth": 3,
        }))
        parts.append(read_key_files.invoke({"repo_path": repo_path}))
        keywords = _extract_search_terms(query)
        for kw in keywords[:2]:
            r = search_code.invoke({
                "pattern": kw, "repo_path": repo_path, "max_results": 10,
            })
            if "未找到" not in r:
                parts.append(r)
        try:
            sem = semantic_search.invoke({
                "query": query, "repo_path": repo_path, "top_k": 3,
            })
            if "未找到" not in sem:
                parts.append(sem)
        except Exception as e:
            logger.warning("语义搜索失败，跳过: %s", e)

    elif skill_type == "generate_skill":
        parts.append(list_directory.invoke({
            "dir_path": repo_path, "repo_path": repo_path, "max_depth": 3,
        }))
        parts.append(read_key_files.invoke({"repo_path": repo_path}))
        keywords = _extract_search_terms(query)
        for kw in keywords[:3]:
            r = search_code.invoke({
                "pattern": kw, "repo_path": repo_path, "max_results": 10,
            })
            if "未找到" not in r:
                parts.append(r)
        try:
            sem = semantic_search.invoke({
                "query": query, "repo_path": repo_path, "top_k": 5,
            })
            if "未找到" not in sem:
                parts.append(sem)
        except Exception as e:
            logger.warning("语义搜索失败，跳过: %s", e)

    context = _truncate_context(parts, max_tokens)
    total_tokens = sum(_estimate_tokens(c) for c in context)
    logger.info("检索完成: %d 段上下文, ~%d tokens", len(context), total_tokens)
    return {"retrieved_context": context}


def _extract_search_terms(query: str) -> list[str]:
    """从用户问题中提取可用于代码搜索的关键词。"""
    import re

    terms: list[str] = []
    for m in re.finditer(r"[A-Z][a-z]+(?:[A-Z][a-z]+)+", query):
        terms.append(m.group())
    for m in re.finditer(r"[a-zA-Z_]\w{3,}", query):
        w = m.group()
        if w not in terms and w.lower() not in _SEARCH_STOP_WORDS:
            terms.append(w)
    if not terms:
        for m in re.finditer(r"[\u4e00-\u9fff]{2,4}", query):
            terms.append(m.group())
    return terms[:5]


_SEARCH_STOP_WORDS = {
    "请", "分析", "帮我", "看看", "什么", "做了", "怎么", "方法", "接口",
    "the", "this", "that", "with", "from", "what", "does", "please",
    "analyze", "method", "function", "class",
}


# ---------------------------------------------------------------------------
# Node 3: Skill 执行
# ---------------------------------------------------------------------------

def skill_executor(state: AgentState) -> dict:
    """调用对应 Skill 执行分析。

    当 skill_type == "generate_skill" 时，运行多个上游分析 Skill 并将结果
    汇总到 analysis_results 中；否则按原有逻辑运行单个 Skill。
    """
    from src.config import get_llm, get_settings
    from src.skills.chain_analysis import ChainAnalysisSkill
    from src.skills.plan_suggestion import PlanSuggestionSkill
    from src.skills.repo_background import RepoBackgroundSkill
    from src.skills.skill_generator import SkillGeneratorSkill

    skill_type = state.get("skill_type", "repo_background")
    repo_path = state.get("repo_path", "")
    query = state.get("user_query", "")
    context = state.get("retrieved_context", [])
    metadata = dict(state.get("metadata", {}))

    logger.info("执行 Skill: %s", skill_type)

    if skill_type == "generate_skill":
        return _execute_generate_skill(query, repo_path, context, metadata)

    skill_map = {
        "repo_background": RepoBackgroundSkill,
        "chain_analysis": ChainAnalysisSkill,
        "plan_suggestion": PlanSuggestionSkill,
    }

    skill_cls = skill_map.get(skill_type)
    if not skill_cls:
        return {
            "skill_result": {},
            "error": f"未知的 Skill 类型: {skill_type}",
            "metadata": metadata,
        }

    try:
        settings = get_settings()
        llm = get_llm(settings)
        metadata["model"] = settings.llm.model_name

        t0 = time.time()
        skill = skill_cls(llm=llm, repo_path=repo_path)
        result = skill.execute(query, context)
        elapsed_ms = int((time.time() - t0) * 1000)

        metadata["skill_elapsed_ms"] = elapsed_ms
        logger.info("Skill 执行完成: %d ms", elapsed_ms)
        return {"skill_result": result, "metadata": metadata}
    except Exception as e:
        logger.exception("Skill 执行失败: %s", e)
        return {
            "skill_result": {},
            "error": f"Skill 执行失败: {e}",
            "metadata": metadata,
        }


def _execute_generate_skill(
    query: str, repo_path: str, context: list[str], metadata: dict
) -> dict:
    """运行上游分析 Skill (repo_background + plan_suggestion) 并汇总结果。"""
    from src.config import get_llm, get_settings
    from src.skills.skill_generator import SkillGeneratorSkill

    try:
        settings = get_settings()
        llm = get_llm(settings)
        metadata["model"] = settings.llm.model_name

        t0 = time.time()
        generator = SkillGeneratorSkill(llm=llm, repo_path=repo_path)
        analysis_results = generator.execute(query, context)
        elapsed_ms = int((time.time() - t0) * 1000)

        metadata["analysis_elapsed_ms"] = elapsed_ms
        logger.info("上游分析完成: %d ms", elapsed_ms)
        return {"analysis_results": analysis_results, "metadata": metadata}
    except Exception as e:
        logger.exception("generate_skill 上游分析失败: %s", e)
        return {
            "analysis_results": {},
            "error": f"上游分析失败: {e}",
            "metadata": metadata,
        }


# ---------------------------------------------------------------------------
# Node 4: 格式化输出（基于 Pydantic Schema）
# ---------------------------------------------------------------------------

from src.schemas.output import (
    ChainAnalysisOutput,
    PlanSuggestionOutput,
    RepoBackgroundOutput,
    SkillSpecOutput,
)

_SKILL_TITLES: dict[str, str] = {
    "repo_background": "仓库背景知识分析",
    "chain_analysis": "代码逻辑链路分析",
    "plan_suggestion": "需求方案建议",
    "generate_skill": "SKILL.md 生成",
}

_SCHEMA_MAP: dict[str, type] = {
    "repo_background": RepoBackgroundOutput,
    "chain_analysis": ChainAnalysisOutput,
    "plan_suggestion": PlanSuggestionOutput,
    "generate_skill": SkillSpecOutput,
}


def formatter(state: AgentState) -> dict:
    """将 skill_result 基于 Pydantic Schema 格式化为 Markdown 报告。"""
    skill_type = state.get("skill_type", "repo_background")
    result = state.get("skill_result", {})
    error = state.get("error")
    query = state.get("user_query", "")
    metadata = state.get("metadata", {})

    title = _SKILL_TITLES.get(skill_type, "分析结果")

    lines: list[str] = [f"# {title}", ""]
    if query:
        lines.extend([f"> **用户问题**: {query}", ""])
    if error:
        lines.extend([f"> **错误**: {error}", ""])

    if result:
        schema = _SCHEMA_MAP.get(skill_type)
        if schema:
            try:
                output = schema.model_validate(result)
                lines.extend(_format_pydantic(output))
            except Exception:
                lines.extend(_format_dict_fallback(result))
        else:
            lines.extend(_format_dict_fallback(result))

    if metadata:
        lines.append("---")
        lines.append("")
        meta_parts: list[str] = []
        if metadata.get("router_method"):
            meta_parts.append(f"路由: {metadata['router_method']}")
        if metadata.get("model"):
            meta_parts.append(f"模型: {metadata['model']}")
        if metadata.get("skill_elapsed_ms"):
            meta_parts.append(f"耗时: {metadata['skill_elapsed_ms']}ms")
        if meta_parts:
            lines.append(f"> {' | '.join(meta_parts)}")
        lines.append("")

    formatted = "\n".join(lines)
    logger.info("格式化完成, 输出长度: %d chars", len(formatted))
    return {"formatted_output": formatted}


def _format_pydantic(output: object) -> list[str]:
    """基于 Pydantic model 的 field info 格式化。"""
    lines: list[str] = []
    for field_name, field_info in type(output).model_fields.items():
        value = getattr(output, field_name)
        label = field_info.description or field_name.replace("_", " ").title()
        lines.append(f"## {label}")
        lines.append("")

        if isinstance(value, list):
            for item in value:
                if hasattr(item, "model_dump"):
                    lines.append(_format_model_item(item, field_name))
                else:
                    lines.append(f"- {item}")
        elif isinstance(value, str):
            lines.append(value)
        else:
            lines.append(str(value))
        lines.append("")

    return lines


def _format_model_item(item: object, parent_field: str) -> str:
    """格式化嵌套的 Pydantic model（Module, CallStep 等）。"""
    d = item.model_dump()
    if "name" in d and "responsibility" in d:
        return f"- **{d['name']}** (`{d.get('path', '')}`): {d['responsibility']}"
    if "caller" in d and "callee" in d:
        desc = d.get("description", "")
        suffix = f" — {desc}" if desc else ""
        return f"- `{d['caller']}` → `{d['callee']}` ({d.get('file_path', '')}){suffix}"
    return f"- {json.dumps(d, ensure_ascii=False)}"


def _format_dict_fallback(result: dict) -> list[str]:
    """字典 fallback 格式化（Schema 验证失败时使用）。"""
    lines: list[str] = []
    for key, value in result.items():
        label = key.replace("_", " ").title()
        lines.append(f"## {label}")
        lines.append("")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"- {json.dumps(item, ensure_ascii=False)}")
                else:
                    lines.append(f"- {item}")
        else:
            lines.append(str(value))
        lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Node 5: Skill Spec 生成（generate_skill 专用）
# ---------------------------------------------------------------------------

def skill_spec_generator(state: AgentState) -> dict:
    """基于上游分析结果生成结构化 Skill 规格。"""
    from src.config import get_llm, get_settings
    from src.skills.skill_generator import SkillGeneratorSkill

    query = state.get("user_query", "")
    repo_path = state.get("repo_path", "")
    analysis_results = state.get("analysis_results", {})
    context = state.get("retrieved_context", [])
    metadata = dict(state.get("metadata", {}))

    logger.info("生成 Skill Spec...")

    try:
        settings = get_settings()
        llm = get_llm(settings)
        t0 = time.time()

        generator = SkillGeneratorSkill(llm=llm, repo_path=repo_path)
        spec = generator.generate_spec(query, analysis_results, context)
        elapsed_ms = int((time.time() - t0) * 1000)

        metadata["spec_elapsed_ms"] = elapsed_ms
        logger.info("Skill Spec 生成完成: %s (%d ms)", spec.get("name"), elapsed_ms)
        return {"skill_spec": spec, "metadata": metadata}
    except Exception as e:
        logger.exception("Skill Spec 生成失败: %s", e)
        return {"skill_spec": {}, "error": f"Spec 生成失败: {e}", "metadata": metadata}


# ---------------------------------------------------------------------------
# Node 6: Skill Markdown 渲染（generate_skill 专用）
# ---------------------------------------------------------------------------

def skill_md_formatter(state: AgentState) -> dict:
    """将结构化 Skill 规格渲染为 SKILL.md 内容并写入 formatted_output。"""
    from src.config import get_llm, get_settings
    from src.skills.skill_generator import SkillGeneratorSkill

    spec = state.get("skill_spec", {})
    repo_path = state.get("repo_path", "")
    metadata = dict(state.get("metadata", {}))
    error = state.get("error")

    if error or not spec:
        fallback = f"# SKILL.md 生成失败\n\n> 错误: {error or '无 Skill Spec 数据'}\n"
        return {"formatted_output": fallback}

    logger.info("渲染 SKILL.md...")

    try:
        settings = get_settings()
        llm = get_llm(settings)
        t0 = time.time()

        generator = SkillGeneratorSkill(llm=llm, repo_path=repo_path)
        markdown = generator.render_markdown(spec)
        elapsed_ms = int((time.time() - t0) * 1000)

        metadata["render_elapsed_ms"] = elapsed_ms
        total_ms = (
            metadata.get("analysis_elapsed_ms", 0)
            + metadata.get("spec_elapsed_ms", 0)
            + elapsed_ms
        )
        metadata["skill_elapsed_ms"] = total_ms

        logger.info("SKILL.md 渲染完成: %d chars (%d ms)", len(markdown), elapsed_ms)
        return {"formatted_output": markdown, "metadata": metadata}
    except Exception as e:
        logger.exception("SKILL.md 渲染失败: %s", e)
        fallback_md = _render_spec_fallback(spec)
        return {"formatted_output": fallback_md, "metadata": metadata}


def _render_spec_fallback(spec: dict) -> str:
    """当 LLM 渲染失败时，基于结构化数据直接生成 Markdown。"""
    name = spec.get("name", "unnamed-skill")
    lines = [f"# {name}", ""]
    lines.append(spec.get("description", ""))
    lines.append("")

    section_map = [
        ("When To Use", "use_when"),
        ("Do Not Use When", "do_not_use_when"),
        ("Required Inputs", "required_inputs"),
        ("Workflow", "workflow_steps"),
        ("Key Paths", "key_paths"),
        ("Commands", "commands"),
        ("Validation", "validation_checks"),
        ("Example Requests", "example_requests"),
        ("Assumptions", "assumptions"),
    ]
    for title, key in section_map:
        items = spec.get(key, [])
        if items:
            lines.append(f"## {title}")
            lines.append("")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Node 7: 人工审核
# ---------------------------------------------------------------------------

def human_review(state: AgentState) -> dict:
    """人工审核中断点。使用 LangGraph interrupt() 暂停执行。"""
    formatted = state.get("formatted_output", "")
    logger.info("进入人工审核节点")

    review_result = interrupt(
        {
            "message": "请审核以下分析结果，输入 approve 确认或 reject 拒绝",
            "output_preview": formatted[:500],
        }
    )

    approved = str(review_result).strip().lower() in ("approve", "yes", "y", "确认", "通过")
    logger.info("审核结果: %s", "通过" if approved else "拒绝")

    if not approved:
        return {
            "review_approved": False,
            "formatted_output": formatted + "\n\n---\n> **审核未通过**，结果仅供参考。",
        }

    return {
        "review_approved": True,
        "formatted_output": formatted + "\n\n---\n> **审核通过**",
    }
