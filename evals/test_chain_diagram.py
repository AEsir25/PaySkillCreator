"""chain_analysis 图生成测试"""

from __future__ import annotations

from src.schemas.output import CallStep, ChainAnalysisOutput, DiagramOutput, GraphEdge, GraphNode
from src.skills.chain_analysis import ChainAnalysisSkill


class _DummyLLM:
    pass


def test_chain_analysis_execute_appends_business_overview(monkeypatch) -> None:
    skill = ChainAnalysisSkill(llm=_DummyLLM(), repo_path="/tmp/repo")

    monkeypatch.setattr(skill, "_run_react_agent", lambda query, context: "trace")
    monkeypatch.setattr(
        skill,
        "_summarize_to_structured",
        lambda query, trace: ChainAnalysisOutput(
            entry_point="PayController.pay",
            call_chain=[
                CallStep(
                    caller="PayController.pay",
                    callee="PayService.execute",
                    file_path="src/pay.py",
                    description="进入支付服务",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        skill,
        "_build_business_overview_diagram",
        lambda query, trace, result: DiagramOutput(
            graph_type="business_overview",
            title="支付流程概览",
            summary="展示支付主链路",
            nodes=[
                GraphNode(id="start", label="开始", node_type="start"),
                GraphNode(id="pay", label="pay", node_type="process"),
            ],
            edges=[GraphEdge(from_node="start", to_node="pay", label="进入支付")],
            mermaid_fallback="flowchart TD\n    start((\"开始\"))\n    start --> pay",
        ),
    )

    result = skill.execute("分析支付流程", None)

    assert "diagrams" in result
    assert len(result["diagrams"]) == 1
    assert result["diagrams"][0]["graph_type"] == "business_overview"
