"""图结构 Schema 测试"""

from __future__ import annotations

from src.schemas.output import DiagramOutput, GraphAnnotation, GraphEdge, GraphNode


def test_business_overview_minimal_schema_is_valid() -> None:
    diagram = DiagramOutput(
        graph_type="business_overview",
        title="支付失败业务流程概览",
        nodes=[
            GraphNode(id="start", label="开始", node_type="start"),
            GraphNode(id="pay", label="pay", node_type="process"),
            GraphNode(id="end", label="失败收银台", node_type="result", category="result"),
        ],
        edges=[
            GraphEdge(from_node="start", to_node="pay", label="进入支付"),
            GraphEdge(from_node="pay", to_node="end", label="支付失败", edge_type="failure"),
        ],
    )

    assert diagram.graph_type == "business_overview"
    assert len(diagram.nodes) == 3
    assert len(diagram.edges) == 2


def test_business_overview_supports_annotations() -> None:
    diagram = DiagramOutput(
        graph_type="business_overview",
        title="支付失败业务流程概览",
        nodes=[GraphNode(id="pay", label="pay", node_type="process")],
        annotations=[
            GraphAnnotation(
                id="note_1",
                anchor_node="pay",
                annotation_type="payload",
                title="情况1",
                content="nextStep=JDP_OPEN_UNIVERSAL_H5",
            )
        ],
    )

    assert diagram.annotations[0].annotation_type == "payload"
