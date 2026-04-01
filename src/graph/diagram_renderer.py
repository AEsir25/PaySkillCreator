"""结构化图的 Mermaid 降级渲染。"""

from __future__ import annotations

from src.schemas.output import DiagramOutput, GraphAnnotation


def render_diagram_to_mermaid(diagram: DiagramOutput) -> str:
    """将结构化图渲染为 Mermaid flowchart。"""
    if diagram.graph_type != "business_overview":
        raise ValueError(f"暂不支持的图类型: {diagram.graph_type}")
    return render_business_overview_to_mermaid(diagram)


def render_business_overview_to_mermaid(diagram: DiagramOutput) -> str:
    lines: list[str] = ["flowchart TD"]

    for node in diagram.nodes:
        node_def = _render_node(node.id, node.label, node.node_type)
        lines.append(f"    {node_def}")

    for index, edge in enumerate(diagram.edges, start=1):
        arrow = _edge_arrow(edge.edge_type)
        label = edge.label or edge.condition
        edge_expr = f"{edge.from_node} {arrow}"
        if label:
            escaped_label = _escape_label(label)
            edge_expr += f'|"{escaped_label}"| '
        edge_expr += edge.to_node
        lines.append(f"    {edge_expr}")

        edge_key = f"edge_{index}"
        for annotation in _annotations_for_edge(diagram.annotations, edge_key):
            note_id = f"ann_{index}_{annotation.id}"
            lines.extend(_render_annotation_block(note_id, annotation))
            lines.append(f"    {note_id} -.-> {edge.to_node}")

    for annotation in diagram.annotations:
        if not annotation.anchor_node:
            continue
        note_id = f"note_{annotation.id}"
        lines.extend(_render_annotation_block(note_id, annotation))
        lines.append(f"    {note_id} -.-> {annotation.anchor_node}")

    return "\n".join(lines)


def _render_node(node_id: str, label: str, node_type: str) -> str:
    escaped = _escape_label(label)
    if node_type == "start":
        return f'{node_id}(("{escaped}"))'
    if node_type == "end":
        return f'{node_id}(("{escaped}"))'
    if node_type == "decision":
        return f'{node_id}{{"{escaped}"}}'
    if node_type == "page":
        return f'{node_id}["{escaped}<br/>H5/Page"]'
    if node_type == "result":
        return f'{node_id}(["{escaped}"])'
    return f'{node_id}["{escaped}"]'


def _edge_arrow(edge_type: str) -> str:
    if edge_type == "retry":
        return "-.->"
    return "-->"


def _escape_label(text: str) -> str:
    return text.replace('"', '\\"').replace("\n", "<br/>")


def _render_annotation_block(node_id: str, annotation: GraphAnnotation) -> list[str]:
    title = f"{annotation.title}: " if annotation.title else ""
    content = _escape_label(title + annotation.content)
    return [f'    {node_id}["{content}"]']


def _annotations_for_edge(annotations: list[GraphAnnotation], edge_key: str) -> list[GraphAnnotation]:
    return [annotation for annotation in annotations if annotation.anchor_edge == edge_key]
