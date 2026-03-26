"""Skill Router 评估测试

测试覆盖:
- 关键词路由准确率
- LLM 路由准确率（需要 API Key）
- 边界 case 处理
"""

from __future__ import annotations

import pytest

from src.graph.nodes import _keyword_route, _llm_route
from src.state import VALID_SKILLS


ROUTER_CASES: list[tuple[str, str]] = [
    # (query, expected_skill_type)
    # --- repo_background ---
    ("这个项目的技术栈是什么", "repo_background"),
    ("请介绍一下这个仓库", "repo_background"),
    ("主要有哪些模块", "repo_background"),
    ("项目的目录结构", "repo_background"),
    ("仓库的整体架构", "repo_background"),
    # --- chain_analysis ---
    ("分析 OrderService.createOrder 的调用链路", "chain_analysis"),
    ("支付接口的执行流程是什么", "chain_analysis"),
    ("帮我看看这个方法调用了哪些下游服务", "chain_analysis"),
    ("PayService.doPay 的代码怎么走的", "chain_analysis"),
    ("分析退款的调用链", "chain_analysis"),
    # --- plan_suggestion ---
    ("如果要添加数字人民币支付方式该怎么改", "plan_suggestion"),
    ("给出一个新增退款功能的实现方案", "plan_suggestion"),
    ("这个需求的影响范围有多大", "plan_suggestion"),
    ("怎么设计一个缓存方案", "plan_suggestion"),
    ("如何实现支付渠道的灰度上线", "plan_suggestion"),
]


class TestKeywordRouter:
    """关键词路由测试"""

    @pytest.mark.parametrize("query,expected", ROUTER_CASES)
    def test_keyword_route_accuracy(self, query: str, expected: str) -> None:
        result = _keyword_route(query)
        assert result in VALID_SKILLS, f"路由返回了无效的 skill: {result}"

    def test_keyword_fallback_defaults_to_repo_background(self) -> None:
        result = _keyword_route("你好世界")
        assert result == "repo_background"

    def test_keyword_route_coverage(self) -> None:
        correct = sum(
            1 for query, expected in ROUTER_CASES
            if _keyword_route(query) == expected
        )
        accuracy = correct / len(ROUTER_CASES)
        print(f"\n关键词路由准确率: {correct}/{len(ROUTER_CASES)} = {accuracy:.1%}")
        assert accuracy >= 0.6, f"关键词路由准确率过低: {accuracy:.1%}"


class TestLLMRouter:
    """LLM 路由测试（需要真实 API）"""

    @pytest.mark.llm
    def test_llm_route_accuracy(self, has_api_key: bool) -> None:
        if not has_api_key:
            pytest.skip("未配置 OPENAI_API_KEY")

        correct = 0
        errors: list[str] = []
        for query, expected in ROUTER_CASES:
            skill, reason = _llm_route(query)
            if skill == expected:
                correct += 1
            else:
                errors.append(f"  [{expected}] '{query}' → {skill} ({reason})")

        accuracy = correct / len(ROUTER_CASES)
        report = f"\nLLM 路由准确率: {correct}/{len(ROUTER_CASES)} = {accuracy:.1%}"
        if errors:
            report += "\n错误分类:\n" + "\n".join(errors)
        print(report)
        assert accuracy >= 0.8, f"LLM 路由准确率过低: {accuracy:.1%}\n{report}"

    @pytest.mark.llm
    def test_llm_route_returns_valid_skill(self, has_api_key: bool) -> None:
        if not has_api_key:
            pytest.skip("未配置 OPENAI_API_KEY")
        skill, reason = _llm_route("分析支付链路")
        if skill is not None:
            assert skill in VALID_SKILLS
            assert len(reason) > 0

    @pytest.mark.llm
    def test_llm_route_with_ambiguous_query(self, has_api_key: bool) -> None:
        if not has_api_key:
            pytest.skip("未配置 OPENAI_API_KEY")
        skill, reason = _llm_route("hello")
        if skill is not None:
            assert skill in VALID_SKILLS
