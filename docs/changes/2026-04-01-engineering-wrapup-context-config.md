# 2026-04-01 工程化收尾与配置收敛

## 背景

本次迭代聚焦两类问题：

- 检索与 Skill 执行之间存在重复工作，导致仓库扫描、关键文件读取和代码搜索重复发生
- 配置层同时保留了 provider registry 和旧式 `llm` 配置路径，维护成本较高

同时，从本次迭代开始，项目建立固定的变更留档机制。

## 核心改动

### 1. 结构化上下文

- 新增 `RetrievedContext`，将预检索结果结构化为目录结构、关键文件、关键词命中、语义命中和组合上下文
- `context_retriever` 统一负责准备上下文，Skill 默认直接消费这份结果
- `repo_background`、`plan_suggestion`、`generate_skill` 不再默认重复读取仓库
- `chain_analysis` 会优先使用预检索线索作为追踪入口提示

### 2. 检索流程工程化收尾

- 将 `context_retriever` 中按 skill 分支散落的逻辑收敛为统一检索计划
- 增加关键词去重，避免同一请求内对重复关键词重复调用代码搜索
- 增加请求内工具结果缓存，减少节点内部重复调用
- 为离线环境补充 token 估算降级逻辑，避免 `tiktoken` 下载失败导致流程中断

### 3. 配置收敛

- `Settings` 收敛为统一主配置对象
- 默认模型统一由 provider registry 推导
- `get_llm()` 改为只根据 `model_id` 和 provider 配置创建实例
- CLI `info` 和 Web `/api/config` 展示统一使用同一套默认模型逻辑

### 4. 文档与流程约定

- 更新 `README.md`、`DEVELOPMENT.md`、`.env.example`
- 新增变更记录约定：每次迭代都在 `docs/changes/` 下新增一份总结

## 测试结果

本次迭代结束后执行：

```bash
.venv/bin/python -m pytest evals -q -k "not llm and not slow"
```

结果：

- `73 passed`
- `8 deselected`

另执行：

```bash
.venv/bin/python -m src.main info
```

结果正常，CLI 配置展示可用。

## 影响

- 现有主流程仍保持兼容，但 Skill 的上下文来源已经统一收敛
- 后续如果引入 RAG 或更复杂的缓存策略，可以优先扩展 `context_retriever`
- 后续每次变更需要同步维护本目录下的新增记录文件
