"""Skill 路由 — Prompt 模板与输出 Schema"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RouterOutput(BaseModel):
    """LLM 路由输出"""

    skill_type: Literal["repo_background", "chain_analysis", "plan_suggestion"] = Field(
        ..., description="选择的 Skill 类型"
    )
    reason: str = Field(..., description="选择该 Skill 的原因（一句话）")


SYSTEM_PROMPT = """\
你是一个任务路由器。根据用户的问题，判断应该使用以下哪个 Skill 来处理。

## 可选 Skill

### repo_background — 仓库背景知识
适用场景：
- 想了解仓库是做什么的、整体架构
- 询问模块职责、目录结构、技术栈
- 想知道项目的入口文件、配置位置
典型问题：
- "请介绍这个仓库"
- "这个项目用了哪些技术栈"
- "主要有哪些模块"

### chain_analysis — 代码逻辑链路分析
适用场景：
- 想了解某个接口/方法/类的代码执行流程
- 想追踪某个功能在代码中是怎么流转的
- 涉及"调用链"、"执行流程"、"代码怎么走的"
典型问题：
- "分析订单提交的代码链路"
- "OrderService.createOrder 做了什么"
- "帮我看看支付接口怎么走的"
- "这个方法调用了哪些下游服务"

### plan_suggestion — 需求方案建议
适用场景：
- 用户提出了一个开发需求，想要实现方案
- 想知道改某个功能需要改哪些文件
- 涉及"怎么实现"、"改动方案"、"影响范围"
典型问题：
- "如果要加一个退款功能该改哪里"
- "给出添加缓存的实现方案"
- "这个需求的影响范围有多大"

## 判断规则

1. 如果用户在问"是什么"、"有什么" → repo_background
2. 如果用户在问"怎么走的"、"调用了什么" → chain_analysis
3. 如果用户在问"怎么做"、"该改哪里" → plan_suggestion
4. 如果不确定，默认选 repo_background
"""

USER_TEMPLATE = "用户问题: {query}"
