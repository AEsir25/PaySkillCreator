"""LangGraph 各节点函数实现

每个节点接收 AgentState，返回要更新的字段 dict。
"""

from __future__ import annotations

import json
import logging

from langgraph.types import interrupt

from src.state import VALID_SKILLS, AgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node 1: Skill 路由
# ---------------------------------------------------------------------------

def skill_router(state: AgentState) -> dict:
    """根据用户输入确定要使用的 Skill 类型。

    优先级: 用户指定 > LLM 意图识别 > 关键词 fallback
    """
    requested = state.get("requested_skill")
    if requested and requested in VALID_SKILLS:
        logger.info("使用用户指定的 Skill: %s", requested)
        return {"skill_type": requested}

    query = state.get("user_query", "")

    skill, reason = _llm_route(query)
    if skill:
        logger.info("LLM 路由: %s (原因: %s)", skill, reason)
        return {"skill_type": skill}

    skill = _keyword_route(query)
    logger.info("关键词 fallback 路由: %s", skill)
    return {"skill_type": skill}


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
    if any(kw in q for kw in ("链路", "调用", "流程", "chain", "trace", "调用链")):
        return "chain_analysis"
    if any(kw in q for kw in ("需求", "方案", "实现", "plan", "设计")):
        return "plan_suggestion"
    return "repo_background"


# ---------------------------------------------------------------------------
# Node 2: 仓库上下文检索
# ---------------------------------------------------------------------------

def context_retriever(state: AgentState) -> dict:
    """根据 skill_type 预检索相关仓库上下文。

    Skill 1/3 在此步收集上下文，Skill 2 的 ReAct Agent 在执行时自主检索。
    """
    from src.tools.code_search import search_code
    from src.tools.file_reader import list_directory, read_key_files

    skill_type = state.get("skill_type", "repo_background")
    repo_path = state.get("repo_path", "")
    query = state.get("user_query", "")

    logger.info("检索上下文: skill=%s, repo=%s", skill_type, repo_path)

    context: list[str] = []

    if skill_type == "repo_background":
        context.append(list_directory.invoke({
            "dir_path": repo_path, "repo_path": repo_path, "max_depth": 3,
        }))
        context.append(read_key_files.invoke({"repo_path": repo_path}))

    elif skill_type == "chain_analysis":
        # ReAct Agent 在 skill_executor 中自主检索，此处做轻量预搜索
        context.append(list_directory.invoke({
            "dir_path": repo_path, "repo_path": repo_path, "max_depth": 2,
        }))
        r = search_code.invoke({
            "pattern": query[:50], "repo_path": repo_path, "max_results": 10,
        })
        context.append(r)

    elif skill_type == "plan_suggestion":
        context.append(list_directory.invoke({
            "dir_path": repo_path, "repo_path": repo_path, "max_depth": 3,
        }))
        context.append(read_key_files.invoke({"repo_path": repo_path}))
        r = search_code.invoke({
            "pattern": query[:50], "repo_path": repo_path, "max_results": 10,
        })
        context.append(r)

    logger.info("检索完成: %d 段上下文", len(context))
    return {"retrieved_context": context}


# ---------------------------------------------------------------------------
# Node 3: Skill 执行
# ---------------------------------------------------------------------------

def skill_executor(state: AgentState) -> dict:
    """调用对应 Skill 执行分析。"""
    from src.config import get_llm
    from src.skills.chain_analysis import ChainAnalysisSkill
    from src.skills.plan_suggestion import PlanSuggestionSkill
    from src.skills.repo_background import RepoBackgroundSkill

    skill_type = state.get("skill_type", "repo_background")
    repo_path = state.get("repo_path", "")
    query = state.get("user_query", "")
    context = state.get("retrieved_context", [])

    logger.info("执行 Skill: %s", skill_type)

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
        }

    try:
        llm = get_llm()
        skill = skill_cls(llm=llm, repo_path=repo_path)
        result = skill.execute(query, context)
        return {"skill_result": result}
    except Exception as e:
        logger.exception("Skill 执行失败: %s", e)
        return {
            "skill_result": {},
            "error": f"Skill 执行失败: {e}",
        }


# ---------------------------------------------------------------------------
# Node 4: 格式化输出
# ---------------------------------------------------------------------------

_SKILL_TITLES: dict[str, str] = {
    "repo_background": "仓库背景知识分析",
    "chain_analysis": "代码逻辑链路分析",
    "plan_suggestion": "需求方案建议",
}

_FIELD_LABELS: dict[str, str] = {
    "overview": "概述",
    "core_modules": "核心模块",
    "key_directories": "关键目录",
    "entry_points": "入口位置",
    "config_extension_points": "配置与扩展点",
    "entry_point": "入口点",
    "call_chain": "调用链",
    "key_branches": "关键分支",
    "dependencies": "依赖模块",
    "risks": "风险点",
    "requirement_understanding": "需求理解",
    "candidate_changes": "候选改动点",
    "recommended_path": "推荐实现路径",
    "impact_scope": "影响范围",
    "risk_analysis": "风险分析",
    "test_suggestions": "验证与测试建议",
}


def formatter(state: AgentState) -> dict:
    """将 skill_result 格式化为 Markdown 报告。"""
    skill_type = state.get("skill_type", "repo_background")
    result = state.get("skill_result", {})
    error = state.get("error")
    query = state.get("user_query", "")

    title = _SKILL_TITLES.get(skill_type, "分析结果")

    lines: list[str] = [f"# {title}", ""]
    if query:
        lines.extend([f"> **用户问题**: {query}", ""])
    if error:
        lines.extend([f"> **错误**: {error}", ""])

    for key, value in result.items():
        label = _FIELD_LABELS.get(key, key.replace("_", " ").title())
        lines.append(f"## {label}")
        lines.append("")

        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if "name" in item and "responsibility" in item:
                        lines.append(f"- **{item['name']}** (`{item.get('path', '')}`): {item['responsibility']}")
                    elif "caller" in item and "callee" in item:
                        desc = item.get("description", "")
                        lines.append(f"- `{item['caller']}` → `{item['callee']}` ({item.get('file_path', '')}){f' — {desc}' if desc else ''}")
                    else:
                        lines.append(f"- {json.dumps(item, ensure_ascii=False)}")
                else:
                    lines.append(f"- {item}")
        elif isinstance(value, str):
            lines.append(value)
        else:
            lines.append(str(value))
        lines.append("")

    formatted = "\n".join(lines)
    logger.info("格式化完成, 输出长度: %d chars", len(formatted))
    return {"formatted_output": formatted}


# ---------------------------------------------------------------------------
# Node 5: 人工审核
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
