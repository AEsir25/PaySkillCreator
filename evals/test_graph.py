"""Graph 端到端集成测试

测试覆盖:
- 完整图构建
- 各 Skill 端到端（需要 LLM API）
- 输出 Schema 校验
"""

from __future__ import annotations

import os

import pytest

from src.graph.builder import build_graph
from src.schemas.output import (
    ChainAnalysisOutput,
    PlanSuggestionOutput,
    RepoBackgroundOutput,
)
from src.state import AgentState, VALID_SKILLS


class TestGraphBuild:
    """图构建测试（不需要 API）"""

    def test_build_graph_no_checkpointer(self) -> None:
        graph = build_graph(checkpointer=False)
        assert graph is not None

    def test_build_graph_with_checkpointer(self) -> None:
        graph = build_graph(checkpointer=True)
        assert graph is not None

    def test_graph_has_all_nodes(self) -> None:
        graph = build_graph(checkpointer=False)
        node_names = set(graph.get_graph().nodes.keys())
        expected = {"skill_router", "context_retriever", "skill_executor", "formatter", "human_review"}
        assert expected.issubset(node_names), f"缺少节点: {expected - node_names}"


class TestGraphE2E:
    """端到端测试（需要真实仓库 + LLM API）"""

    @pytest.fixture
    def graph(self):
        return build_graph(checkpointer=False)

    @pytest.mark.llm
    @pytest.mark.slow
    def test_repo_background_e2e(self, graph, repo_path: str, has_api_key: bool) -> None:
        if not has_api_key:
            pytest.skip("未配置 OPENAI_API_KEY")

        state: AgentState = {
            "repo_path": repo_path,
            "user_query": "请介绍这个仓库的整体架构",
            "requested_skill": "repo_background",
            "need_review": False,
            "metadata": {},
        }
        result = graph.invoke(state)

        assert result.get("skill_type") == "repo_background"
        assert result.get("formatted_output")
        assert len(result["formatted_output"]) > 100

        skill_result = result.get("skill_result", {})
        if skill_result:
            output = RepoBackgroundOutput.model_validate(skill_result)
            assert len(output.overview) > 10
            assert len(output.core_modules) > 0

    @pytest.mark.llm
    @pytest.mark.slow
    def test_chain_analysis_e2e(self, graph, repo_path: str, has_api_key: bool) -> None:
        if not has_api_key:
            pytest.skip("未配置 OPENAI_API_KEY")

        state: AgentState = {
            "repo_path": repo_path,
            "user_query": "分析支付下单的调用链路",
            "requested_skill": "chain_analysis",
            "need_review": False,
            "metadata": {},
        }
        result = graph.invoke(state)

        assert result.get("skill_type") == "chain_analysis"
        assert result.get("formatted_output")

        skill_result = result.get("skill_result", {})
        if skill_result:
            output = ChainAnalysisOutput.model_validate(skill_result)
            assert len(output.entry_point) > 0

    @pytest.mark.llm
    @pytest.mark.slow
    def test_plan_suggestion_e2e(self, graph, repo_path: str, has_api_key: bool) -> None:
        if not has_api_key:
            pytest.skip("未配置 OPENAI_API_KEY")

        state: AgentState = {
            "repo_path": repo_path,
            "user_query": "添加一个退款功能需要改哪些地方",
            "requested_skill": "plan_suggestion",
            "need_review": False,
            "metadata": {},
        }
        result = graph.invoke(state)

        assert result.get("skill_type") == "plan_suggestion"
        assert result.get("formatted_output")

        skill_result = result.get("skill_result", {})
        if skill_result:
            output = PlanSuggestionOutput.model_validate(skill_result)
            assert len(output.requirement_understanding) > 10
            assert len(output.candidate_changes) > 0

    @pytest.mark.llm
    def test_llm_auto_routing(self, graph, repo_path: str, has_api_key: bool) -> None:
        """验证不指定 skill 时 LLM 能正确路由"""
        if not has_api_key:
            pytest.skip("未配置 OPENAI_API_KEY")

        test_cases = [
            ("这个仓库的技术栈是什么", "repo_background"),
            ("分析 createOrder 的调用链", "chain_analysis"),
            ("如何添加一个新的支付渠道", "plan_suggestion"),
        ]

        for query, expected_skill in test_cases:
            state: AgentState = {
                "repo_path": repo_path,
                "user_query": query,
                "requested_skill": None,
                "need_review": False,
                "metadata": {},
            }
            result = graph.invoke(state)
            actual_skill = result.get("skill_type")
            assert actual_skill in VALID_SKILLS
            print(f"  '{query}' → {actual_skill} (期望 {expected_skill})")

    def test_error_handling_invalid_skill(self) -> None:
        """验证无效 skill 被正确处理"""
        graph = build_graph(checkpointer=False)
        state: AgentState = {
            "repo_path": "/tmp/nonexistent",
            "user_query": "测试",
            "requested_skill": "invalid_skill",
            "need_review": False,
            "metadata": {},
        }
        result = graph.invoke(state)
        assert result.get("formatted_output") is not None
