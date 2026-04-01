# 2026-04-01 业务流程概览图第二阶段前端自定义渲染

## 背景

第一阶段已经完成：

- `business_overview` 结构化图输出
- Mermaid fallback
- Web 基于 Mermaid 展示

本次迭代继续实现第二阶段，将 Web 端升级为更接近业务流程图示例的自定义渲染。

## 核心改动

### 1. 前端自定义 SVG 渲染

在 `web/static/app.js` 中新增：

- 自定义布局计算
- 节点层级分布
- 边路径和边标签绘制
- 注释气泡框与虚线指向
- 不同节点类型的视觉区分

当前支持的视觉元素包括：

- 开始/结束节点
- 普通业务步骤节点
- 页面节点
- 结果节点
- 条件分支节点
- 注释气泡

### 2. Mermaid 兜底保留

Web 端现在优先使用结构化图渲染自定义业务流程图：

- 成功时展示自定义 SVG
- 同时保留 Mermaid fallback 的折叠查看入口
- 如果结构化图布局失败，再退回 Mermaid 渲染

### 3. 样式增强

在 `web/static/style.css` 中补充：

- 图例
- 自定义图卡片背景
- 自定义 SVG 容器样式
- Mermaid fallback 折叠样式
- 移动端适配

## 当前效果

相比第一阶段，业务流程概览图在 Web 端现在更接近“业务流程图”而不是“普通 Markdown 图”：

- 更清晰地区分节点类型
- 更突出业务步骤与条件分支
- 更接近示例图里的注释气泡表达

## 验证结果

执行：

```bash
node --check web/static/app.js
.venv/bin/python -m pytest evals -q -k "not llm and not slow"
```

结果：

- 前端脚本语法检查通过
- 非 LLM 回归：`81 passed, 9 deselected`
