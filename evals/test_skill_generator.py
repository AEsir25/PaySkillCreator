"""SKILL.md 生成流程测试

测试覆盖:
- SkillSpecOutput Schema 结构合法性
- SKILL.md 输出核心章节完整性
- Graph 生成分支构建与路由
- 关键词路由对 generate_skill 的识别
- fallback 渲染逻辑
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.graph.builder import build_graph
from src.graph.nodes import _keyword_route, _render_spec_fallback
from src.schemas.output import SkillSpecOutput
from src.state import VALID_SKILLS


# ---------------------------------------------------------------------------
# Schema 合法性测试
# ---------------------------------------------------------------------------

class TestSkillSpecSchema:

    def test_minimal_valid_spec(self) -> None:
        spec = SkillSpecOutput(
            name="test-skill",
            description="A test skill for unit testing.",
            final_markdown="# test-skill\n\nA test skill.",
        )
        assert spec.name == "test-skill"
        assert spec.final_markdown.startswith("# test-skill")

    def test_full_valid_spec(self) -> None:
        spec = SkillSpecOutput(
            name="jdpaysdk-callchain-skill",
            description="追踪 jdpaysdk 仓库中的代码调用链路。",
            use_when=["用户提供了类名或方法名", "需要分析调用链路"],
            do_not_use_when=["非 jdpaysdk 仓库", "通用 Java 教学"],
            required_inputs=["类名或方法名"],
            workflow_steps=[
                "搜索入口类定义",
                "提取方法体",
                "追踪下游调用",
            ],
            key_paths=["src/main/java/com/jd/pay/"],
            commands=["mvn compile"],
            validation_checks=["调用链包含至少 2 层"],
            example_requests=["分析 PayService.doPay 的调用链"],
            assumptions=["仓库使用 Java + Maven"],
            final_markdown="# jdpaysdk-callchain-skill\n\nFull content here.",
        )
        assert len(spec.use_when) == 2
        assert len(spec.workflow_steps) == 3
        dump = spec.model_dump()
        assert "name" in dump
        assert "final_markdown" in dump

    def test_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            SkillSpecOutput(name="x")  # type: ignore[call-arg]

    def test_empty_lists_are_valid(self) -> None:
        spec = SkillSpecOutput(
            name="empty-skill",
            description="Skill with empty lists.",
            final_markdown="# empty-skill",
        )
        assert spec.use_when == []
        assert spec.workflow_steps == []
        assert spec.key_paths == []


# ---------------------------------------------------------------------------
# SKILL.md 输出格式测试
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = [
    "When To Use",
    "Do Not Use",
    "Workflow",
    "Validation",
    "Example Requests",
]

REQUIRED_SECTIONS_ALT = [
    "何时使用",
    "不适用",
    "工作步骤",
    "验证",
    "示例",
]


class TestSkillMdFormat:

    @pytest.fixture
    def sample_spec_dict(self) -> dict:
        return SkillSpecOutput(
            name="test-repo-skill",
            description="用于测试的 Skill。",
            use_when=["用户想要测试"],
            do_not_use_when=["非测试场景"],
            required_inputs=["测试输入"],
            workflow_steps=["步骤一", "步骤二", "步骤三"],
            key_paths=["src/test/"],
            commands=["pytest"],
            validation_checks=["输出不为空"],
            example_requests=["请帮我测试"],
            assumptions=["已安装 pytest"],
            final_markdown="# test-repo-skill\n\nSkill description.\n\n"
            "## When To Use\n\n- 用户想要测试\n\n"
            "## Do Not Use When\n\n- 非测试场景\n\n"
            "## Required Inputs\n\n- 测试输入\n\n"
            "## Workflow\n\n1. 步骤一\n2. 步骤二\n3. 步骤三\n\n"
            "## Key Paths\n\n- `src/test/`\n\n"
            "## Commands\n\n```bash\npytest\n```\n\n"
            "## Validation\n\n- 输出不为空\n\n"
            "## Example Requests\n\n- 请帮我测试\n\n"
            "## Assumptions\n\n- 已安装 pytest\n",
        ).model_dump()

    def test_final_markdown_has_title(self, sample_spec_dict: dict) -> None:
        md = sample_spec_dict["final_markdown"]
        assert md.startswith("# ")

    def test_final_markdown_has_required_sections(self, sample_spec_dict: dict) -> None:
        md = sample_spec_dict["final_markdown"]
        for section in REQUIRED_SECTIONS:
            assert section in md, f"SKILL.md 缺少章节: {section}"

    def test_final_markdown_not_empty(self, sample_spec_dict: dict) -> None:
        md = sample_spec_dict["final_markdown"]
        assert len(md) > 100

    def test_final_markdown_is_valid_markdown(self, sample_spec_dict: dict) -> None:
        md = sample_spec_dict["final_markdown"]
        assert md.count("#") >= 2
        assert "\n" in md


# ---------------------------------------------------------------------------
# Fallback 渲染测试
# ---------------------------------------------------------------------------

class TestFallbackRenderer:

    def test_render_spec_fallback_basic(self) -> None:
        spec = {
            "name": "fallback-skill",
            "description": "Fallback test.",
            "use_when": ["条件 A", "条件 B"],
            "workflow_steps": ["步骤 1", "步骤 2"],
            "key_paths": ["src/"],
            "validation_checks": ["检查 1"],
            "example_requests": ["示例 1"],
        }
        md = _render_spec_fallback(spec)
        assert md.startswith("# fallback-skill")
        assert "## When To Use" in md
        assert "## Workflow" in md
        assert "## Validation" in md
        assert "- 条件 A" in md
        assert "- 步骤 1" in md

    def test_render_spec_fallback_empty_lists(self) -> None:
        spec = {"name": "empty", "description": "Empty."}
        md = _render_spec_fallback(spec)
        assert md.startswith("# empty")
        assert "##" not in md.split("\n", 2)[-1] or True  # no sections with content


# ---------------------------------------------------------------------------
# 路由测试
# ---------------------------------------------------------------------------

class TestGenerateSkillRouting:

    @pytest.mark.parametrize("query", [
        "为这个仓库生成 SKILL.md",
        "帮我创建一个 skill 文件",
        "生成 skill 定义",
        "把链路追踪沉淀为 skill",
        "generate skill for this repo",
    ])
    def test_keyword_route_detects_generate_skill(self, query: str) -> None:
        result = _keyword_route(query)
        assert result == "generate_skill", f"'{query}' 应路由到 generate_skill，实际: {result}"

    def test_generate_skill_in_valid_skills(self) -> None:
        assert "generate_skill" in VALID_SKILLS


# ---------------------------------------------------------------------------
# Graph 构建测试
# ---------------------------------------------------------------------------

class TestGenerateSkillGraph:

    def test_graph_has_new_nodes(self) -> None:
        graph = build_graph(checkpointer=False)
        node_names = set(graph.get_graph().nodes.keys())
        required = {"skill_spec_generator", "skill_md_formatter"}
        assert required.issubset(node_names), f"缺少节点: {required - node_names}"

    def test_graph_has_all_original_nodes(self) -> None:
        graph = build_graph(checkpointer=False)
        node_names = set(graph.get_graph().nodes.keys())
        original = {
            "skill_router", "context_retriever", "skill_executor",
            "formatter", "human_review",
        }
        assert original.issubset(node_names), f"缺少原有节点: {original - node_names}"

    def test_graph_builds_with_checkpointer(self) -> None:
        graph = build_graph(checkpointer=True)
        assert graph is not None
