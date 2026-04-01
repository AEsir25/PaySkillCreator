"""各 Skill 输出 Schema 定义"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 分析型 Skill 输出 Schema
# ---------------------------------------------------------------------------

class Module(BaseModel):
    """模块描述"""

    name: str = Field(..., description="模块名称")
    path: str = Field(..., description="模块路径")
    responsibility: str = Field(..., description="模块职责")


class RepoBackgroundOutput(BaseModel):
    """Skill 1: 仓库背景知识输出"""

    overview: str = Field(..., description="仓库整体功能概述")
    core_modules: list[Module] = Field(default_factory=list, description="核心模块列表")
    key_directories: list[str] = Field(default_factory=list, description="关键目录说明")
    entry_points: list[str] = Field(default_factory=list, description="主要入口位置")
    config_extension_points: list[str] = Field(default_factory=list, description="配置与扩展点")


class CallStep(BaseModel):
    """调用链中的一步"""

    caller: str = Field(..., description="调用方 (类名.方法名)")
    callee: str = Field(..., description="被调用方 (类名.方法名)")
    file_path: str = Field(..., description="所在文件路径")
    description: str = Field(default="", description="说明")


DiagramType = Literal[
    "business_overview", "call_chain", "sequence_interaction", "state_transition"
]
GraphNodeType = Literal["start", "end", "process", "decision", "page", "result"]
GraphNodeCategory = Literal["backend", "frontend", "user_action", "external", "result"]
GraphEdgeType = Literal["transition", "success", "failure", "retry", "timeout"]
GraphAnnotationType = Literal["note", "rule", "payload", "risk"]


class GraphNode(BaseModel):
    """结构化图节点。"""

    id: str = Field(..., description="节点唯一 ID")
    label: str = Field(..., description="节点展示名称")
    node_type: GraphNodeType = Field(..., description="节点类型")
    category: GraphNodeCategory = Field(default="backend", description="节点分类")
    description: str = Field(default="", description="节点描述")
    source_refs: list[str] = Field(default_factory=list, description="节点对应的源码引用")


class GraphEdge(BaseModel):
    """结构化图边。"""

    from_node: str = Field(..., description="起始节点 ID")
    to_node: str = Field(..., description="目标节点 ID")
    label: str = Field(default="", description="边文本")
    edge_type: GraphEdgeType = Field(default="transition", description="边类型")
    condition: str = Field(default="", description="边条件说明")


class GraphAnnotation(BaseModel):
    """结构化图注释。"""

    id: str = Field(..., description="注释唯一 ID")
    anchor_node: str = Field(default="", description="注释绑定节点 ID")
    anchor_edge: str = Field(default="", description="注释绑定边 ID")
    annotation_type: GraphAnnotationType = Field(default="note", description="注释类型")
    title: str = Field(default="", description="注释标题")
    content: str = Field(..., description="注释内容")
    display_hint: str = Field(default="callout", description="展示提示")


class DiagramOutput(BaseModel):
    """统一图输出。"""

    graph_type: DiagramType = Field(..., description="图类型")
    title: str = Field(..., description="图标题")
    summary: str = Field(default="", description="图摘要")
    nodes: list[GraphNode] = Field(default_factory=list, description="图节点")
    edges: list[GraphEdge] = Field(default_factory=list, description="图边")
    annotations: list[GraphAnnotation] = Field(default_factory=list, description="图注释")
    mermaid_fallback: str = Field(default="", description="Mermaid 降级渲染内容")


class ChainAnalysisOutput(BaseModel):
    """Skill 2: 代码逻辑链路分析输出"""

    entry_point: str = Field(..., description="入口点")
    call_chain: list[CallStep] = Field(default_factory=list, description="主要调用链")
    key_branches: list[str] = Field(default_factory=list, description="关键分支逻辑")
    dependencies: list[str] = Field(default_factory=list, description="依赖模块")
    risks: list[str] = Field(default_factory=list, description="风险点与不确定点")
    entry_evidence: list[str] = Field(default_factory=list, description="用于定位入口点的证据")
    unresolved_points: list[str] = Field(default_factory=list, description="尚未确认的链路问题")
    search_strategy_used: list[str] = Field(default_factory=list, description="本次追链使用的搜索策略")
    diagrams: list[DiagramOutput] = Field(default_factory=list, description="结构化图输出")


class PlanSuggestionOutput(BaseModel):
    """Skill 3: 需求方案建议输出"""

    requirement_understanding: str = Field(..., description="需求理解")
    candidate_changes: list[str] = Field(default_factory=list, description="候选改动点")
    recommended_path: str = Field(..., description="推荐实现路径")
    impact_scope: list[str] = Field(default_factory=list, description="影响范围")
    risk_analysis: list[str] = Field(default_factory=list, description="风险分析")
    test_suggestions: list[str] = Field(default_factory=list, description="验证与测试建议")


# ---------------------------------------------------------------------------
# SKILL.md 生成 Schema
# ---------------------------------------------------------------------------

class SkillSpecOutput(BaseModel):
    """SKILL.md 生成的结构化 Skill 规格（Codex/Cursor 兼容格式）"""

    name: str = Field(
        ...,
        description="Skill 名称，小写+连字符，如 jdpaysdk-callchain-skill",
    )
    description: str = Field(
        ...,
        description="YAML frontmatter description，含 Skill 用途和触发条件，50-200 词",
    )
    use_when: list[str] = Field(
        default_factory=list,
        description="触发条件列表：什么情况下应该使用此 Skill",
    )
    do_not_use_when: list[str] = Field(
        default_factory=list,
        description="排除条件：什么情况下不该使用此 Skill",
    )
    required_inputs: list[str] = Field(
        default_factory=list,
        description="用户必须提供的输入，例如类名、方法名、需求描述",
    )
    background_knowledge: list[str] = Field(
        default_factory=list,
        description="面向 AI coding 的场景背景知识压缩",
    )
    business_glossary: list[str] = Field(
        default_factory=list,
        description="场景相关的业务术语表",
    )
    scene_entry_points: list[str] = Field(
        default_factory=list,
        description="该业务场景在仓库中的入口点或候选入口",
    )
    typical_call_chains: list[str] = Field(
        default_factory=list,
        description="典型调用链摘要，包含入口到下游的关键路径",
    )
    workflow_steps: list[str] = Field(
        default_factory=list,
        description="Agent 执行此 Skill 时的具体工作步骤（按顺序，祈使句）",
    )
    key_paths: list[str] = Field(
        default_factory=list,
        description="仓库中与此 Skill 相关的关键文件和目录路径",
    )
    commands: list[str] = Field(
        default_factory=list,
        description="可能用到的构建/运行/测试命令",
    )
    validation_checks: list[str] = Field(
        default_factory=list,
        description="如何验证 Skill 执行结果是否正确",
    )
    debug_checklist: list[str] = Field(
        default_factory=list,
        description="调试与排查该场景时优先检查的事项",
    )
    search_keywords: list[str] = Field(
        default_factory=list,
        description="分析该场景时建议优先检索的关键词或别名",
    )
    example_requests: list[str] = Field(
        default_factory=list,
        description="用户可能提出的示例请求（2-4 个具体例子）",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="前置假设与约束条件",
    )
    final_markdown: str = Field(
        ...,
        description="完整 SKILL.md 内容，以 YAML frontmatter 开头，后接 Markdown body",
    )
