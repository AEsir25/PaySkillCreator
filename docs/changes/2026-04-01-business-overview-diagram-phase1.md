# 2026-04-01 业务流程概览图第一阶段

## 背景

本次迭代为 `chain_analysis` 增加第一阶段的流程图能力，目标是让代码链路分析结果不仅包含文字报告，还能输出一张可直接展示的“业务流程概览图”。

本次只实现第一阶段：

- 统一图 schema
- `business_overview` 图类型
- Mermaid fallback 渲染
- Web 端透传并展示图

## 核心改动

### 1. 统一图模型

在 `src/schemas/output.py` 中新增：

- `DiagramOutput`
- `GraphNode`
- `GraphEdge`
- `GraphAnnotation`

并在 `ChainAnalysisOutput` 中新增 `diagrams` 字段。

### 2. Mermaid 降级渲染

新增 `src/graph/diagram_renderer.py`：

- 支持将 `business_overview` 结构化图渲染为 Mermaid flowchart
- 当前作为 CLI / Web 的通用降级展示格式

### 3. `chain_analysis` 图生成

在 `src/skills/chain_analysis.py` 中新增业务流程概览图提炼步骤：

- 先生成原有结构化链路分析结果
- 再基于结果与分析 trace 生成 `business_overview`
- 成功时写入 `diagrams`
- 同时生成 `mermaid_fallback`

### 4. Formatter 与 Web 展示

- `formatter` 会在链路分析结果中追加“业务流程概览图”章节
- `web/server.py` 会在 SSE `result` 事件中透传 `diagrams`
- 前端在 `web/static/app.js` 中优先渲染 `business_overview`
- `web/static/index.html` 引入 Mermaid
- `web/static/style.css` 补充图卡片样式

## 当前支持的图类型

- `business_overview`

定义：

- 该图用于表达业务步骤、页面跳转、条件分支、失败回流和补充说明
- 不是严格的方法级调用图

## 测试结果

执行：

```bash
.venv/bin/python -m pytest evals -q -k "not llm and not slow"
```

结果：

- `78 passed`
- `8 deselected`

## 后续可扩展方向

- 增加 `call_chain` 图类型
- 增加 `sequence_interaction` 图类型
- 增加 `state_transition` 图类型
- 将 Web 端从 Mermaid fallback 升级为自定义业务流程图渲染
