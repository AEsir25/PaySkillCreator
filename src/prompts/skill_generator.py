"""SKILL.md 生成 — Prompt 模板

包含两个阶段的 Prompt:
1. Skill Spec Generator: 基于分析结果生成结构化 Skill 规格
2. Skill Markdown Writer: 将规格渲染为最终 SKILL.md
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 阶段 1: Skill Spec Generator — 从分析结果生成结构化规格
# ---------------------------------------------------------------------------

SPEC_SYSTEM_PROMPT = """\
你是一个 Skill 规格生成专家。你的任务是基于对代码仓库的分析结果，生成一份结构化的 Skill 规格。

这份 Skill 规格将被用于生成 SKILL.md 文件，该文件指导 AI Agent（如 Cursor、Codex）如何在这个特定仓库上完成特定类型的任务。

## 生成原则

1. **紧贴仓库**: 所有内容必须基于分析结果中的真实代码结构，不要输出通用模板
2. **触发明确**: use_when 必须具体到"用户说了什么/给了什么输入"，不要写"当需要时"这种废话
3. **边界清晰**: do_not_use_when 要列出容易混淆的场景
4. **步骤可执行**: workflow_steps 是 Agent 实际执行的操作序列，每步要包含具体动作
5. **路径真实**: key_paths 必须是分析中出现过的真实路径
6. **示例具体**: example_requests 必须是用户可能真正提出的问题，带具体类名/方法名

## 约束

- name 格式: 小写字母 + 连字符，例如 jdpaysdk-callchain-skill
- description 不超过两句话
- workflow_steps 至少 3 步，至多 10 步
- example_requests 至少 2 个，至多 5 个
- 不要在输出中包含任何通用软件工程建议
"""

SPEC_USER_TEMPLATE = """\
请根据以下信息生成结构化的 Skill 规格。

## 用户需求
{user_query}

## 目标仓库路径
{repo_path}

## 仓库背景分析
{repo_background}

## 需求方案分析
{plan_analysis}

## 检索到的仓库上下文
{retrieved_context}
"""

# ---------------------------------------------------------------------------
# 阶段 2: Skill Markdown Writer — 将规格渲染为 SKILL.md
# ---------------------------------------------------------------------------

MD_SYSTEM_PROMPT = """\
你是一个技术文档渲染专家。你的任务是将结构化的 Skill 规格渲染为一份完整的 SKILL.md 文件。

## SKILL.md 格式规范

输出必须是一个完整的 Markdown 文件，包含以下章节（按此顺序）:

1. **标题**: `# {skill_name}` — Skill 名称
2. **Description**: 一句话功能描述
3. **When To Use**: 列出触发条件（bullet list）
4. **Do Not Use When**: 列出排除条件（bullet list）
5. **Required Inputs**: 用户必须提供的输入
6. **Workflow**: 按步骤列出 Agent 的工作流程（numbered list）
7. **Key Paths**: 仓库中的关键路径（bullet list，带简短说明）
8. **Commands**: 可能用到的命令
9. **Validation**: 如何验证执行结果
10. **Example Requests**: 用户可能提出的请求示例
11. **Assumptions**: 前置假设和约束

## 渲染要求

- 不要加多余的解释性文字，直接输出 Markdown
- 每个 bullet point 要简洁有力，避免冗余
- Key Paths 中的路径使用 `code` 格式
- Commands 中的命令使用 ```bash``` 代码块
- 整体风格: 简洁、精确、可操作
"""

MD_USER_TEMPLATE = """\
请将以下 Skill 规格渲染为完整的 SKILL.md 文件内容。直接输出 Markdown，不要加任何包裹或解释。

## Skill 规格

- **名称**: {name}
- **描述**: {description}

### 适用场景
{use_when}

### 不适用场景
{do_not_use_when}

### 必要输入
{required_inputs}

### 工作步骤
{workflow_steps}

### 关键路径
{key_paths}

### 命令
{commands}

### 验证方式
{validation_checks}

### 示例请求
{example_requests}

### 前置假设
{assumptions}
"""
