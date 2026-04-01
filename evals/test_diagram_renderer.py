"""图渲染测试"""

from __future__ import annotations

from src.graph.diagram_renderer import render_business_overview_to_mermaid
from src.schemas.output import DiagramOutput, GraphAnnotation, GraphEdge, GraphNode


def test_render_business_overview_to_mermaid() -> None:
    diagram = DiagramOutput(
        graph_type="business_overview",
        title="支付失败业务流程概览",
        nodes=[
            GraphNode(id="start", label="开始", node_type="start"),
            GraphNode(id="prepare", label="preparePay", node_type="process"),
            GraphNode(id="decision", label="支付失败?", node_type="decision"),
            GraphNode(id="result", label="失败收银台", node_type="result", category="result"),
        ],
        edges=[
            GraphEdge(from_node="start", to_node="prepare", label="进入支付"),
            GraphEdge(from_node="prepare", to_node="decision", label="执行支付"),
            GraphEdge(from_node="decision", to_node="result", label="失败", edge_type="failure"),
        ],
        annotations=[
            GraphAnnotation(
                id="a1",
                anchor_node="decision",
                annotation_type="note",
                title="情况1",
                content="下发失败推荐收银台",
            )
        ],
    )

    mermaid = render_business_overview_to_mermaid(diagram)

    assert mermaid.startswith("flowchart TD")
    assert 'prepare["preparePay"]' in mermaid
    assert '|"失败"|' in mermaid
    assert "情况1: 下发失败推荐收银台" in mermaid
