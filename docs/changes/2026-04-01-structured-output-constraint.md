# 2026-04-01 structured output 统一约束沉淀

## 背景

在完成 JSON 兼容性修复后，为了避免后续新增代码再次绕开兼容层，本次将该经验沉淀为项目内的明确约束。

## 本次改动

### 1. 提炼公共 helper

新增：

- `src/llm/json_prompt.py`

提供：

- `ensure_json_keyword()`
- `build_json_messages()`

用途：

- 统一处理 provider 对 `json/JSON` 关键词的要求
- 让路由与其他非 Skill 场景复用同一套消息构造逻辑

### 2. 收敛现有调用点

- `src/graph/nodes.py` 中的 `_llm_route()` 改为复用 `build_json_messages()`
- `src/skills/base.py` 中的 structured output 调用改为复用 `build_json_messages()` / `ensure_json_keyword()`

### 3. 建立开发约束

在 `DEVELOPMENT.md` 中明确：

- 禁止在业务代码里直接裸调 `with_structured_output()` 后自行拼 messages
- 路由类场景统一复用 `src/llm/json_prompt.py`
- Skill 类场景统一复用 `BaseSkill._call_llm_structured()`
- 新增 structured output 入口时，必须补 provider 兼容性测试

## 测试结果

执行：

```bash
.venv/bin/python -m pytest evals/test_json_prompt_helper.py evals/test_base_skill_structured_output.py evals/test_router_structured_output.py -q
.venv/bin/python -m pytest evals -q -k "not llm and not slow"
```

结果：

- helper/兼容专项测试：通过
- 非 LLM 回归：`81 passed, 9 deselected`
