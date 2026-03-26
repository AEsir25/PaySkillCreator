"""LangGraph 各节点函数实现

每个节点接收 AgentState，返回要更新的字段 dict。
当前为 stub 实现，后续阶段逐步替换为真实逻辑。
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

    - 如果用户通过 CLI 直接指定了 skill，直接采用
    - 否则由 LLM 做意图识别（当前 stub: 默认 repo_background）
    """
    requested = state.get("requested_skill")

    if requested and requested in VALID_SKILLS:
        logger.info("使用用户指定的 Skill: %s", requested)
        return {"skill_type": requested}

    # TODO: 阶段 4 — 接入 LLM 意图识别
    query = state.get("user_query", "")
    skill = _stub_route(query)
    logger.info("路由结果 (stub): %s", skill)
    return {"skill_type": skill}


def _stub_route(query: str) -> str:
    """基于关键词的简单 stub 路由，后续替换为 LLM。"""
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
    """根据 skill_type 检索相关仓库上下文。

    TODO: 阶段 2/5 — 接入 tools 层做真实检索
    """
    skill_type = state.get("skill_type", "repo_background")
    repo_path = state.get("repo_path", "")
    query = state.get("user_query", "")

    logger.info("检索上下文 (stub): skill=%s, repo=%s", skill_type, repo_path)

    context = [
        f"[stub] skill_type={skill_type}",
        f"[stub] repo_path={repo_path}",
        f"[stub] query={query}",
        "[stub] 真实上下文将在阶段 2/5 中接入",
    ]
    return {"retrieved_context": context}


# ---------------------------------------------------------------------------
# Node 3: Skill 执行
# ---------------------------------------------------------------------------

def skill_executor(state: AgentState) -> dict:
    """调用对应 Skill 执行分析。

    TODO: 阶段 3 — 接入真实 Skill 实现
    """
    skill_type = state.get("skill_type", "repo_background")
    query = state.get("user_query", "")

    logger.info("执行 Skill (stub): %s", skill_type)

    result = _STUB_RESULTS.get(skill_type, _STUB_RESULTS["repo_background"])
    result = {**result, "_stub": True, "_query": query}
    return {"skill_result": result}


_STUB_RESULTS: dict[str, dict] = {
    "repo_background": {
        "overview": "这是一个示例仓库概述（stub 数据）",
        "core_modules": [
            {"name": "module-a", "path": "src/module_a", "responsibility": "核心业务逻辑"},
            {"name": "module-b", "path": "src/module_b", "responsibility": "数据访问层"},
        ],
        "key_directories": ["src/", "config/", "docs/"],
        "entry_points": ["src/main.py"],
        "config_extension_points": ["config/settings.yaml"],
    },
    "chain_analysis": {
        "entry_point": "Controller.handleRequest()",
        "call_chain": [
            {
                "caller": "Controller.handleRequest",
                "callee": "Service.process",
                "file_path": "src/controller.java",
                "description": "入口调用",
            },
            {
                "caller": "Service.process",
                "callee": "Dao.query",
                "file_path": "src/service.java",
                "description": "业务调用数据层",
            },
        ],
        "key_branches": ["if (orderType == REFUND) → RefundService"],
        "dependencies": ["module-a", "module-b"],
        "risks": ["Dao.query 存在 N+1 查询风险"],
    },
    "plan_suggestion": {
        "requirement_understanding": "用户希望实现某功能（stub 数据）",
        "candidate_changes": ["src/service.java", "src/controller.java"],
        "recommended_path": "在 Service 层新增方法，Controller 层增加路由",
        "impact_scope": ["module-a", "module-b"],
        "risk_analysis": ["需要回归测试现有接口"],
        "test_suggestions": ["单元测试覆盖新增方法", "集成测试验证端到端流程"],
    },
}


# ---------------------------------------------------------------------------
# Node 4: 格式化输出
# ---------------------------------------------------------------------------

_SKILL_TITLES: dict[str, str] = {
    "repo_background": "仓库背景知识分析",
    "chain_analysis": "代码逻辑链路分析",
    "plan_suggestion": "需求方案建议",
}


def formatter(state: AgentState) -> dict:
    """将 skill_result 格式化为 Markdown 报告。

    TODO: 阶段 5 — 使用 Pydantic Schema 做严格格式化
    """
    skill_type = state.get("skill_type", "repo_background")
    result = state.get("skill_result", {})

    title = _SKILL_TITLES.get(skill_type, "分析结果")
    is_stub = result.pop("_stub", False)
    query = result.pop("_query", "")

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    if query:
        lines.append(f"> **用户问题**: {query}")
        lines.append("")
    if is_stub:
        lines.append("> ⚠️ 当前为 stub 数据，真实分析将在后续阶段实现")
        lines.append("")

    for key, value in result.items():
        section_title = key.replace("_", " ").title()
        lines.append(f"## {section_title}")
        lines.append("")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"- **{item.get('name', item.get('caller', ''))}**: {json.dumps(item, ensure_ascii=False)}")
                else:
                    lines.append(f"- {item}")
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
    """人工审核中断点。

    使用 LangGraph interrupt() 暂停执行，等待外部确认。
    CLI 模式下直接与用户交互。
    """
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
            "formatted_output": formatted + "\n\n---\n> ❌ **审核未通过**，结果仅供参考。",
        }

    return {
        "review_approved": True,
        "formatted_output": formatted + "\n\n---\n> ✅ **审核通过**",
    }
