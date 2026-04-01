# 开发指南

## 环境准备

### 前置要求

- macOS (Apple Silicon)
- [uv](https://docs.astral.sh/uv/) — Python 包与环境管理器

### 初始化环境

```bash
# 安装 Python 3.11（如尚未安装）
uv python install 3.11

# 创建虚拟环境
uv venv --python 3.11

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
uv pip install -r requirements.txt
```

### 验证环境

```bash
# 确认 Python 版本
.venv/bin/python --version
# 期望输出: Python 3.11.x

# 验证核心依赖
.venv/bin/python -c "import langgraph, langchain, pydantic; print('OK')"

# 测试 CLI
.venv/bin/python -m src.main --help
.venv/bin/python -m src.main info
```

## 配置

复制 `.env.example` 为 `.env`，填入实际配置：

```bash
cp .env.example .env
```

必填项：
- 至少一个 Provider 的 API Key，例如 `DASHSCOPE_API_KEY`
- `MODEL_NAME` — 默认模型 ID
- `TARGET_REPO_PATH` — 目标分析仓库的本地路径

兼容项：
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` 仍可作为 DashScope 的兼容变量使用
- 新环境请优先使用 `.env.example` 中的 Provider 专属变量

## 运行

```bash
# 查看配置
.venv/bin/python -m src.main info

# 执行分析任务
.venv/bin/python -m src.main run "请介绍这个仓库的核心模块"

# 指定仓库路径
.venv/bin/python -m src.main run "分析订单提交流程" --repo /path/to/repo

# 指定 Skill 类型
.venv/bin/python -m src.main run "给出实现方案" --skill plan_suggestion

# 启用人工审核
.venv/bin/python -m src.main run "分析代码链路" --review
```

## 项目结构

```
src/
├── main.py          # CLI 入口
├── config.py        # Provider 注册表与统一配置入口
├── state.py         # LangGraph State
├── graph/           # LangGraph 工作流编排
├── skills/          # 3 个 Skill 实现
├── tools/           # 代码分析工具
├── prompts/         # Prompt 模板
└── schemas/         # 输入/输出 Schema（含结构化 RetrievedContext）
evals/               # 评估用例
```

当前执行职责划分：
- `context_retriever` 统一准备目录、关键文件、关键词命中、语义命中
- Skill 层默认直接消费结构化上下文，不再重复读取仓库
- `config.py` 统一负责默认模型选择和 provider 凭据解析

## 变更记录

- 每次迭代都需要同步更新原有文档，并在 `docs/changes/` 下新增一份变更总结
- 文件命名格式：`YYYY-MM-DD-简要概括.md`
- 变更总结建议包含：修改背景、核心改动、测试结果、后续影响

## 测试

```bash
# 运行不需要 LLM 的本地测试（Tools、路由关键词、Graph 构建）
.venv/bin/python -m pytest evals/ -v -k "not llm and not slow"

# 运行包含 LLM 的全量测试（需要 .env 中配置 API Key）
.venv/bin/python -m pytest evals/ -v -s

# 只运行路由准确率评估
.venv/bin/python -m pytest evals/test_router.py -v -s
```

### 测试矩阵

| 测试文件 | 覆盖范围 | 是否需要 LLM |
|---|---|---|
| `test_tools.py` | file_reader / code_search / tree_parser | 否 |
| `test_context_retriever.py` | 结构化上下文检索 | 否 |
| `test_skills_context_usage.py` | Skill 复用上下文 | 否 |
| `test_config.py` | Provider 配置解析 | 否 |
| `test_router.py` | 关键词路由 + LLM 路由准确率 | 部分 |
| `test_graph.py` | Graph 构建 + 3 Skill 端到端 | 部分 |

### 评估指标

- **关键词路由准确率**: 86.7% (13/15)
- **LLM 路由准确率**: 100% (15/15)
- **端到端测试**: 3/3 Skill 全部通过

## 当前进度

- [x] 阶段 0: 项目脚手架
- [x] 阶段 1: State + Graph 骨架
- [x] 阶段 2: Tools 层
- [x] 阶段 3: Skills 实现
- [x] 阶段 4: Skill Router LLM 化
- [x] 阶段 5: Retriever + Formatter 优化
- [x] 阶段 6: 端到端测试
- [x] 阶段 7: 评估框架
