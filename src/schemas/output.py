"""各 Skill 输出 Schema 定义"""

from __future__ import annotations

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


class ChainAnalysisOutput(BaseModel):
    """Skill 2: 代码逻辑链路分析输出"""

    entry_point: str = Field(..., description="入口点")
    call_chain: list[CallStep] = Field(default_factory=list, description="主要调用链")
    key_branches: list[str] = Field(default_factory=list, description="关键分支逻辑")
    dependencies: list[str] = Field(default_factory=list, description="依赖模块")
    risks: list[str] = Field(default_factory=list, description="风险点与不确定点")


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
