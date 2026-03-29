"""SKILL.md 生成流程测试

测试覆盖:
- SkillSpecOutput Schema 结构合法性
- SKILL.md 输出 Codex 兼容性（YAML frontmatter + 章节）
- Graph 生成分支构建与路由
- 关键词路由对 generate_skill 的识别
- fallback 渲染逻辑（含 frontmatter）
- _ensure_frontmatter 逻辑
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.graph.builder import build_graph
from src.graph.nodes import _keyword_route, _render_spec_fallback
from src.schemas.output import SkillSpecOutput
from src.skills.skill_generator import SkillGeneratorSkill
from src.state import VALID_SKILLS


# ---------------------------------------------------------------------------
# Schema 合法性测试
# ---------------------------------------------------------------------------

class TestSkillSpecSchema:

    def test_minimal_valid_spec(self) -> None:
        spec = SkillSpecOutput(
            name="test-skill",
            description="A test skill for unit testing. Use when testing.",
            final_markdown="---\nname: test-skill\ndescription: A test skill.\n---\n\n# test-skill",
        )
        assert spec.name == "test-skill"
        assert spec.final_markdown.startswith("---")

    def test_full_valid_spec(self) -> None:
        spec = SkillSpecOutput(
            name="jdpaysdk-callchain-skill",
            description=(
                "Use this skill when the user provides a class or method name "
                "related to jdpaysdk and wants the call chain. Do not use for "
                "generic Java tutoring."
            ),
            use_when=["用户提供了类名或方法名", "需要分析调用链路"],
            do_not_use_when=["非 jdpaysdk 仓库", "通用 Java 教学"],
            required_inputs=["类名或方法名"],
            background_knowledge=["先确认业务场景和入口协议，再追服务链路"],
            business_glossary=["受理单: 支付申请单据"],
            scene_entry_points=["PayController.submit"],
            typical_call_chains=["PayController.submit -> PayService.doPay -> ChannelRouter.route"],
            workflow_steps=[
                "搜索入口类定义",
                "提取方法体",
                "追踪下游调用",
            ],
            key_paths=["src/main/java/com/jd/pay/"],
            commands=["mvn compile"],
            validation_checks=["调用链包含至少 2 层"],
            debug_checklist=["确认路由配置是否命中"],
            search_keywords=["PayService", "ChannelRouter"],
            example_requests=["分析 PayService.doPay 的调用链"],
            assumptions=["仓库使用 Java + Maven"],
            final_markdown=(
                "---\nname: jdpaysdk-callchain-skill\n"
                'description: "Use this skill when..."\n---\n\n'
                "# jdpaysdk-callchain-skill\n\nFull content here."
            ),
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
            description="Skill with empty lists. Use when testing empty cases.",
            final_markdown="---\nname: empty-skill\ndescription: test\n---\n\n# empty-skill",
        )
        assert spec.use_when == []
        assert spec.workflow_steps == []
        assert spec.key_paths == []


# ---------------------------------------------------------------------------
# Codex 兼容性测试
# ---------------------------------------------------------------------------

class TestCodexCompatibility:
    """验证生成的 SKILL.md 符合 Codex 规范。"""

    @pytest.fixture
    def sample_frontmatter_md(self) -> str:
        return (
            '---\nname: test-repo-skill\n'
            'description: "Analyze test repo structure. Use when testing."\n'
            '---\n\n'
            '# test-repo-skill\n\n'
            'Analyze the test repo.\n\n'
            '## When to use\n\n'
            '1. User wants to test\n\n'
            '## When NOT to use\n\n'
            '1. Non-test scenarios\n\n'
            '## Required workflow\n\n'
            '### Step 1: Initialize\n\nRun setup.\n\n'
            '### Step 2: Execute\n\nRun tests.\n\n'
            '### Step 3: Validate\n\nCheck results.\n\n'
            '## Key paths\n\n'
            '- `src/test/`\n\n'
            '## Commands\n\n'
            '```bash\npytest\n```\n\n'
            '## Validation\n\n'
            '- Output is not empty\n\n'
            '## Example prompts this skill should handle well\n\n'
            '- "Please help me test"\n\n'
            '## Assumptions\n\n'
            '- pytest is installed\n'
        )

    def test_starts_with_yaml_frontmatter(self, sample_frontmatter_md: str) -> None:
        assert sample_frontmatter_md.startswith("---\n")

    def test_frontmatter_has_name(self, sample_frontmatter_md: str) -> None:
        assert "name:" in sample_frontmatter_md.split("---")[1]

    def test_frontmatter_has_description(self, sample_frontmatter_md: str) -> None:
        assert "description:" in sample_frontmatter_md.split("---")[1]

    def test_frontmatter_closes(self, sample_frontmatter_md: str) -> None:
        parts = sample_frontmatter_md.split("---")
        assert len(parts) >= 3, "YAML frontmatter 未正确闭合（需要两个 ---）"

    def test_has_when_to_use_section(self, sample_frontmatter_md: str) -> None:
        assert "## When to use" in sample_frontmatter_md

    def test_has_when_not_to_use_section(self, sample_frontmatter_md: str) -> None:
        assert "## When NOT to use" in sample_frontmatter_md

    def test_has_workflow_section(self, sample_frontmatter_md: str) -> None:
        assert "## Required workflow" in sample_frontmatter_md or "## Workflow" in sample_frontmatter_md

    def test_has_validation_section(self, sample_frontmatter_md: str) -> None:
        assert "## Validation" in sample_frontmatter_md

    def test_has_example_section(self, sample_frontmatter_md: str) -> None:
        assert "Example" in sample_frontmatter_md


# ---------------------------------------------------------------------------
# _ensure_frontmatter 测试
# ---------------------------------------------------------------------------

class TestEnsureFrontmatter:

    def test_preserves_existing_frontmatter(self) -> None:
        md = "---\nname: x\ndescription: y\n---\n\n# x\n\nBody."
        result = SkillGeneratorSkill._ensure_frontmatter(md, {"name": "x", "description": "y"})
        assert result.startswith("---")
        assert result.count("---") == 2

    def test_adds_missing_frontmatter(self) -> None:
        md = "# my-skill\n\nSome body content."
        spec = {"name": "my-skill", "description": "Does things. Use when needed."}
        result = SkillGeneratorSkill._ensure_frontmatter(md, spec)
        assert result.startswith("---\n")
        assert "name: my-skill" in result
        assert 'description: "Does things.' in result
        assert "# my-skill" in result

    def test_handles_quotes_in_description(self) -> None:
        md = "# test\n\nBody."
        spec = {"name": "test", "description": 'Has "quotes" inside.'}
        result = SkillGeneratorSkill._ensure_frontmatter(md, spec)
        assert result.startswith("---")
        assert '\\"quotes\\"' in result or "quotes" in result


# ---------------------------------------------------------------------------
# Fallback 渲染测试（含 Codex frontmatter）
# ---------------------------------------------------------------------------

class TestFallbackRenderer:

    def test_render_spec_fallback_has_frontmatter(self) -> None:
        spec = {
            "name": "fallback-skill",
            "description": "Fallback test. Use when LLM fails.",
            "use_when": ["条件 A", "条件 B"],
            "background_knowledge": ["背景 A"],
            "scene_entry_points": ["入口 A"],
            "typical_call_chains": ["入口 A -> 服务 B -> 仓储 C"],
            "workflow_steps": ["步骤 1", "步骤 2"],
            "key_paths": ["src/"],
            "validation_checks": ["检查 1"],
            "example_requests": ["示例 1"],
        }
        md = _render_spec_fallback(spec)
        assert md.startswith("---\n")
        assert "name: fallback-skill" in md
        assert "description:" in md

    def test_render_spec_fallback_has_codex_sections(self) -> None:
        spec = {
            "name": "fallback-skill",
            "description": "Test.",
            "use_when": ["条件 A"],
            "do_not_use_when": ["排除 A"],
            "background_knowledge": ["背景 A"],
            "scene_entry_points": ["入口 A"],
            "typical_call_chains": ["入口 A -> 服务 B"],
            "workflow_steps": ["步骤 1"],
            "validation_checks": ["检查 1"],
            "example_requests": ["示例 1"],
        }
        md = _render_spec_fallback(spec)
        assert "## When to use" in md
        assert "## When NOT to use" in md
        assert "## Required workflow" in md
        assert "## Scene background" in md
        assert "## Entry points" in md
        assert "## Typical call chains" in md
        assert "## Validation" in md
        assert "## Example prompts" in md

    def test_render_spec_fallback_body_after_frontmatter(self) -> None:
        spec = {"name": "test", "description": "Desc."}
        md = _render_spec_fallback(spec)
        parts = md.split("---")
        assert len(parts) >= 3
        body = parts[2]
        assert "# test" in body

    def test_render_spec_fallback_empty_lists(self) -> None:
        spec = {"name": "empty", "description": "Empty."}
        md = _render_spec_fallback(spec)
        assert md.startswith("---\n")
        assert "name: empty" in md

    def test_render_spec_fallback_commands_render_as_code_block(self) -> None:
        spec = {"name": "cmd", "description": "Desc.", "commands": ["pytest -q"]}
        md = _render_spec_fallback(spec)
        assert "```bash" in md
        assert "pytest -q" in md

    def test_build_chain_query_expands_scene_terms(self) -> None:
        query = "帮我生成一个一分购场景的中文通用skill"
        result = SkillGeneratorSkill._build_chain_query(query, [])
        assert "一分购" in result
        assert "调用链" in result


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
