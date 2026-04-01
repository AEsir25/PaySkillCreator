# PaySkillCreator

面向**单仓库**的分析型 Agent —— 将对代码库的理解与分析能力沉淀为一组可复用的 Skills，并支持**直接生成 `SKILL.md` 文件**。

基于 **LangGraph** 工作流 + **LLM 意图路由** + **代码分析工具链** 构建。

---

## 快速开始

### 1. 环境准备

```bash
# 安装 uv（如尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 Python 3.11
uv python install 3.11

# 克隆项目并进入目录
cd PaySkillCreator

# 创建虚拟环境 + 安装依赖
uv venv --python 3.11
uv pip install -r requirements.txt

# 安装测试依赖（可选）
uv pip install pytest
```

### 2. 配置 API Key 与目标仓库

```bash
cp .env.example .env
```

编辑 `.env` 文件，至少填入一个 Provider 的 API Key，以及目标仓库路径：

```properties
# 推荐：阿里百炼（DashScope）
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 可选：MiniMax / OpenAI Native
MINIMAX_API_KEY=
OPENAI_NATIVE_API_KEY=

# 默认模型 ID（必须属于已启用 Provider）
MODEL_NAME=qwen-plus

# 要分析的目标代码仓库的本地绝对路径
TARGET_REPO_PATH=/path/to/your/java/project
```

兼容说明：
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` 仍可作为 DashScope 的兼容变量使用
- 新接入环境建议优先使用 `.env.example` 中的 Provider 专属变量

### 3. 验证安装

```bash
# 查看当前配置
.venv/bin/python -m src.main info

# 查看 CLI 帮助
.venv/bin/python -m src.main --help
```

正常输出示例：

```
╭──────────────────── 当前配置 ────────────────────╮
│ 目标仓库: /Users/you/IdeaProjects/your-project    │
│ 默认模型: qwen-plus                               │
│ 最大上下文 Tokens: 8000                            │
│ 人工审核: 关闭                                     │
╰──────────────────────────────────────────────────╯
```

---

## 两种使用方式

PaySkillCreator 提供 **Web UI** 和 **CLI** 两种使用方式，功能完全等价。

当前默认执行链路为：
- `skill_router` 负责路由
- `context_retriever` 统一准备结构化上下文
- Skill 负责消费上下文并完成分析
- `formatter` 或 `skill_md_formatter` 负责最终渲染

变更记录约定：
- 每次迭代除了更新原有文档，还会在 `docs/changes/` 下新增一份变更总结
- 文件名格式为 `YYYY-MM-DD-简要概括.md`

### 方式一：Web UI（推荐）

```bash
# 启动 Web 服务
.venv/bin/python -m uvicorn web.server:app --host 127.0.0.1 --port 8000
```

浏览器访问 **http://localhost:8000** ，在左侧填入仓库路径，在对话框中输入问题即可。

支持特性：
- 实时进度显示（路由 → 检索 → 分析 → 格式化，SSE 流式推送）
- Markdown 结构化结果渲染
- Skill 选择（自动路由 / 手动指定 / 生成 SKILL.md）
- 对话式交互，可连续提问
- 快捷问题一键发送
- **SKILL.md 生成**: 选择"生成 SKILL.md"后，可在对话页面中直接预览并下载/复制生成的 Skill 文件

### 方式二：CLI

### 基本语法

```bash
# 分析模式
.venv/bin/python -m src.main run "<你的问题>" [选项]

# 生成 SKILL.md 模式
.venv/bin/python -m src.main generate-skill "<Skill 需求描述>" [选项]
```

### `run` 命令参数

| 参数 | 缩写 | 说明 | 默认值 |
|---|---|---|---|
| `query` | — | 问题或任务描述（必填） | — |
| `--repo` | `-r` | 目标仓库路径（覆盖 .env） | .env 中的 TARGET_REPO_PATH |
| `--skill` | `-s` | 指定 Skill 类型（不指定则自动路由） | 自动 |
| `--review` | — | 启用人工审核 | 关闭 |
| `--verbose` | `-v` | 启用详细日志 | 关闭 |

### `generate-skill` 命令参数

| 参数 | 缩写 | 说明 | 默认值 |
|---|---|---|---|
| `query` | — | Skill 需求描述（必填） | — |
| `--repo` | `-r` | 目标仓库路径（覆盖 .env） | .env 中的 TARGET_REPO_PATH |
| `--output` | `-o` | SKILL.md 输出文件路径（不指定则输出到终端） | 终端输出 |
| `--review` | — | 启用人工审核 | 关闭 |
| `--verbose` | `-v` | 启用详细日志 | 关闭 |

---

## 核心能力

PaySkillCreator 提供 **3 个分析型 Skill** 和 **1 个生成能力**：

| 能力 | 说明 | 定位 |
|---|---|---|
| `repo_background` | 仓库背景知识 | 分析型（也作为 SKILL.md 生成的上游素材） |
| `chain_analysis` | 代码逻辑链路分析 | 分析型（也作为 SKILL.md 生成的上游素材） |
| `plan_suggestion` | 需求方案建议 | 分析型（也作为 SKILL.md 生成的上游素材） |
| `generate_skill` | **生成 SKILL.md** | 产物型 — 汇总分析结果，输出可落盘的 Skill 文件 |

---

### Skill 1: 仓库背景知识 (`repo_background`)

**用途**: 了解一个仓库整体是做什么的、有哪些模块、技术栈是什么。

```bash
# 自动路由（LLM 会识别出这是 repo_background 类型）
.venv/bin/python -m src.main run "这个项目的技术栈和整体架构是什么"

# 手动指定 Skill
.venv/bin/python -m src.main run "请介绍这个仓库" --skill repo_background
```

**适合的问题**:
- "请介绍一下这个仓库"
- "主要有哪些模块，各自职责是什么"
- "项目入口在哪里"
- "技术栈和依赖有哪些"

**输出内容**: 仓库概述 → 核心模块列表 → 关键目录 → 入口位置 → 配置扩展点

---

### Skill 2: 代码逻辑链路分析 (`chain_analysis`)

**用途**: 追踪某个接口 / 方法 / 类的代码调用链路，理解代码执行流程。

```bash
# 自动路由
.venv/bin/python -m src.main run "分析支付下单的调用链路"

# 手动指定
.venv/bin/python -m src.main run "分析 PaywayRoutingService 的调用链路" --skill chain_analysis
```

**适合的问题**:
- "分析 OrderService.createOrder 做了什么"
- "支付接口的代码怎么走的"
- "这个方法调用了哪些下游服务"
- "帮我看看退款流程的调用链"

**输出内容**: 入口点 → 主调用链（含文件路径）→ 关键分支逻辑 → 依赖模块 → 风险点 → **业务流程概览图**

> 此 Skill 内部使用 **ReAct Agent** 多轮调用代码分析工具，自动搜索、解析、追踪。分析深度 3-5 层，耗时相对较长（约 60s）。

当前已支持的图类型：
- `business_overview`: 业务流程概览图，强调业务步骤、页面跳转、条件分支、失败回流与补充说明

说明：
- `business_overview` 是业务语义图，不等于严格的方法调用图
- 当前 Web 端会优先渲染该图的自定义业务流程图，Mermaid 作为降级兜底
- 后续可在相同结构下继续扩展 `call_chain`、`sequence_interaction`、`state_transition`

---

### Skill 3: 需求方案建议 (`plan_suggestion`)

**用途**: 提出一个开发需求，获得可行的实现方案、改动点和风险分析。

```bash
# 自动路由
.venv/bin/python -m src.main run "如何添加数字人民币支付方式"

# 手动指定
.venv/bin/python -m src.main run "为支付收银台添加数字人民币支付方式" --skill plan_suggestion
```

**适合的问题**:
- "如果要加一个退款功能该改哪里"
- "给出添加缓存的实现方案"
- "这个需求的影响范围有多大"
- "如何实现支付渠道的灰度上线"

**输出内容**: 需求理解 → 候选改动点 → 推荐实现路径 → 影响范围 → 风险分析 → 测试建议

---

### 生成 SKILL.md (`generate_skill`)

**用途**: 将对仓库的理解沉淀为一个可复用的 `SKILL.md` 文件，可直接放入项目目录，供 AI Agent（如 Cursor、Codex）使用。

#### CLI 方式

```bash
# 输出到终端
.venv/bin/python -m src.main generate-skill "为这个仓库生成代码链路追踪的 Skill"

# 写入文件
.venv/bin/python -m src.main generate-skill "为支付仓库生成调用链分析 Skill" --output SKILL.md

# 指定其他仓库
.venv/bin/python -m src.main generate-skill "生成支付渠道开发 Skill" --repo /path/to/other/repo --output SKILL.md
```

#### 通过 `run` 命令（自动路由或手动指定）

```bash
# 自动路由 — LLM 识别出需要生成 SKILL.md
.venv/bin/python -m src.main run "为这个仓库生成一个 SKILL.md"

# 手动指定
.venv/bin/python -m src.main run "生成链路追踪 Skill" --skill generate_skill
```

#### Web UI 方式

在 Web 页面左侧选择 **"生成 SKILL.md"**，或点击快捷按钮，输入 Skill 需求描述。生成完成后页面会显示：
- 完整的 SKILL.md 预览（Markdown 渲染）
- **下载 SKILL.md** 按钮
- **复制内容** 按钮

**工作流程**: 统一预检索上下文 → 自动运行 `repo_background` + `plan_suggestion` + `chain_analysis` 上游 Skill → 生成结构化 Skill 规格 → 渲染为完整 SKILL.md

**输出内容**: Skill 名称 → 功能描述 → 适用场景 → 不适用场景 → 必要输入 → 工作步骤 → 关键路径 → 命令 → 验证方式 → 示例请求 → 前置假设

---

## 自动路由 vs 手动指定

**推荐使用自动路由**（不加 `--skill` 参数），LLM 会根据问题内容自动判断使用哪个 Skill：

| 你问的问题类型 | 路由到的 Skill |
|---|---|
| "是什么"、"有什么" → 了解仓库 | `repo_background` |
| "怎么走的"、"调用了什么" → 追踪代码 | `chain_analysis` |
| "怎么做"、"该改哪里" → 实现方案 | `plan_suggestion` |
| "生成 SKILL.md"、"沉淀为 skill" → 生成 Skill 文件 | `generate_skill` |

如果 LLM 路由不符合预期，可以通过 `--skill` 强制指定。

---

## 高级用法

### 分析不同仓库

```bash
# 临时指定另一个仓库（不修改 .env）
.venv/bin/python -m src.main run "介绍这个项目" --repo /path/to/another/repo
```

### 启用人工审核

```bash
# 分析完成后暂停，等待审核确认
.venv/bin/python -m src.main run "分析支付链路" --review
```

### 查看详细日志

```bash
# 开启 verbose 模式，输出每个节点的执行日志
.venv/bin/python -m src.main run "介绍这个仓库" -v
```

### 环境变量配置项

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | LLM API Key（**必填**）| — |
| `OPENAI_BASE_URL` | API 接口地址 | `https://api.openai.com/v1` |
| `MODEL_NAME` | 模型名称 | `gpt-4o` |
| `TARGET_REPO_PATH` | 目标仓库路径（**必填**）| — |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `MAX_CONTEXT_TOKENS` | 最大上下文 token 数 | `8000` |
| `NEED_HUMAN_REVIEW` | 默认启用人工审核 | `false` |

---

## 工作流架构

### 分析模式（repo_background / chain_analysis / plan_suggestion）

```
用户输入
  │
  ▼
┌──────────────┐
│ Skill Router │ ← LLM 意图识别 / 关键词 fallback / 用户指定
└──────┬───────┘
       ▼
┌──────────────────┐
│ Context Retriever│ ← 目录扫描 + 关键文件 + 代码搜索 + 语义搜索
└──────┬───────────┘
       ▼
┌──────────────────┐
│ Skill Executor   │ ← 调用对应 Skill（LLM + 工具链）
└──────┬───────────┘
       ▼
┌──────────────┐
│  Formatter   │ ← Pydantic Schema → Markdown 结构化输出
└──────┬───────┘
       ▼
┌──────────────────┐
│ Human Review     │ ← 可选，需要时暂停等待审核
└──────┬───────────┘
       ▼
     输出结果
```

### SKILL.md 生成模式（generate_skill）

```
用户输入 "为这个仓库生成 SKILL.md"
  │
  ▼
┌──────────────┐
│ Skill Router │ ← 识别为 generate_skill
└──────┬───────┘
       ▼
┌──────────────────┐
│ Context Retriever│ ← 全面检索（目录 + 关键文件 + 代码 + 语义）
└──────┬───────────┘
       ▼
┌──────────────────┐
│ Skill Executor   │ ← 运行 repo_background + plan_suggestion 两个上游 Skill
└──────┬───────────┘
       ▼
┌──────────────────────┐
│ Skill Spec Generator │ ← LLM: 分析结果 → 结构化 SkillSpec（12 字段）
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ Skill MD Formatter   │ ← SkillSpec → 渲染为完整 SKILL.md Markdown
└──────┬───────────────┘
       ▼
┌──────────────────┐
│ Human Review     │ ← 可选
└──────┬───────────┘
       ▼
     输出 SKILL.md
```

---

## 项目结构

```
PaySkillCreator/
├── src/
│   ├── main.py              # CLI 入口（run / generate-skill / info）
│   ├── config.py            # 配置管理（读取 .env）
│   ├── state.py             # LangGraph AgentState 定义
│   ├── graph/
│   │   ├── builder.py       # StateGraph 构建与编排（含条件分支）
│   │   └── nodes.py         # 7 个节点函数实现
│   ├── skills/
│   │   ├── base.py          # Skill 抽象基类
│   │   ├── repo_background.py
│   │   ├── chain_analysis.py
│   │   ├── plan_suggestion.py
│   │   └── skill_generator.py  # SKILL.md 生成（编排上游 Skill + Spec + 渲染）
│   ├── tools/
│   │   ├── file_reader.py   # 文件读取 / 目录扫描
│   │   ├── code_search.py   # 代码搜索（ripgrep）
│   │   ├── tree_parser.py   # AST 解析（tree-sitter）
│   │   └── vector_search.py # 语义搜索（FAISS + TF-IDF）
│   ├── prompts/
│   │   ├── router.py        # 路由 Prompt
│   │   ├── repo_background.py
│   │   ├── chain_analysis.py
│   │   ├── plan_suggestion.py
│   │   └── skill_generator.py  # SKILL.md 生成 Prompt（Spec + Markdown 两阶段）
│   └── schemas/
│       ├── input.py
│       └── output.py        # 输出 Schema（含 SkillSpecOutput）
├── web/
│   ├── server.py            # FastAPI 后端（API + SSE 流式）
│   └── static/
│       ├── index.html       # 前端页面（含 SKILL.md 生成入口）
│       ├── style.css        # 暗色主题样式
│       └── app.js           # 前端交互逻辑（含下载/复制 SKILL.md）
├── evals/                   # 测试与评估
│   ├── test_tools.py        # 工具层单元测试
│   ├── test_router.py       # 路由准确率评估
│   ├── test_graph.py        # 端到端集成测试
│   └── test_skill_generator.py  # SKILL.md 生成流程测试
├── .env.example             # 配置模板
├── requirements.txt         # 依赖清单
├── pyproject.toml           # 项目配置
└── DEVELOPMENT.md           # 开发者指南
```

---

## 测试

```bash
# 运行本地测试（不需要 API Key，49 项）
.venv/bin/python -m pytest evals/ -v -k "not llm and not slow"

# 运行全量测试（需要 .env 配置好）
.venv/bin/python -m pytest evals/ -v -s

# 只运行 SKILL.md 生成测试
.venv/bin/python -m pytest evals/test_skill_generator.py -v

# 只运行路由准确率评估
.venv/bin/python -m pytest evals/test_router.py -v -s -k "llm"
```

---

## 常见问题

### Q: 支持哪些 LLM？

任何兼容 OpenAI 接口格式的 LLM 都可以使用，包括：
- **阿里云百炼**: qwen-plus / qwen-max / qwen-turbo
- **OpenAI**: gpt-4o / gpt-4o-mini
- **本地部署**: 通过 Ollama / vLLM 等暴露的 OpenAI 兼容接口

只需在 `.env` 中修改 `OPENAI_BASE_URL` 和 `MODEL_NAME`。

### Q: 支持分析哪些语言的仓库？

当前主要针对 **Java** 仓库优化（AST 解析、符号搜索模式等），但基础功能（目录扫描、文本搜索、LLM 分析）对任何语言仓库都可用。

### Q: chain_analysis 为什么比较慢？

chain_analysis 内部使用 **ReAct Agent** 进行多轮工具调用（搜索代码 → 解析结构 → 提取方法 → 追踪调用），通常需要 5-15 轮 LLM 交互。使用 `qwen-plus` 通常需要 30-60 秒。

### Q: 如何提高分析质量？

1. **使用更强的模型**: `qwen-max` 或 `gpt-4o` 对复杂链路分析效果更好
2. **增大上下文窗口**: 在 `.env` 中调大 `MAX_CONTEXT_TOKENS`（如 16000）
3. **问题描述尽量具体**: "分析 OrderService.createOrder 的调用链" 比 "分析下单流程" 更精确

### Q: 出现 "配置错误: OPENAI_API_KEY is required" 怎么办？

确保 `.env` 文件存在且 `OPENAI_API_KEY` 已正确填入。可以运行 `info` 命令检查：

```bash
.venv/bin/python -m src.main info
```
