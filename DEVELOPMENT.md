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
- `OPENAI_API_KEY` — LLM API Key
- `TARGET_REPO_PATH` — 目标分析仓库的本地路径

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
├── config.py        # 全局配置
├── state.py         # LangGraph State
├── graph/           # LangGraph 工作流编排
├── skills/          # 3 个 Skill 实现
├── tools/           # 代码分析工具
├── prompts/         # Prompt 模板
└── schemas/         # 输入/输出 Schema
evals/               # 评估用例
```

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
