# 2026-04-01 structured output JSON 兼容加固

## 背景

在修复路由层的 JSON 兼容问题后，继续排查了项目内所有 structured output 调用路径，确认是否还存在同类 provider 兼容风险。

排查范围包括：

- `with_structured_output()`
- JSON 约束 prompt
- structured output fallback

## 结论

项目内真正的 structured output 入口共有两类：

- 路由 `_llm_route()`
- `BaseSkill._call_llm_structured()`

其中路由层已在上一轮修复，这次继续对 `BaseSkill` 做了同样的显式 JSON 关键字加固。

## 本次改动

- 在 `src/skills/base.py` 中新增 `_ensure_json_keyword()`
- `BaseSkill._call_llm_structured()` 现在会同时确保 system prompt 和 user message 都包含 `JSON` 指令
- fallback 到纯文本 JSON 解析时，也复用相同保护逻辑
- 新增测试 `evals/test_base_skill_structured_output.py`

## 影响

- 所有 Skill 的 structured output 调用路径都已经统一兼容这类 provider 要求
- 后续新增 Skill 时，只要继续走 `BaseSkill._call_llm_structured()`，无需再单独处理该问题

## 测试结果

执行：

```bash
.venv/bin/python -m pytest evals/test_base_skill_structured_output.py evals/test_router_structured_output.py -q
.venv/bin/python -m pytest evals -q -k "not llm and not slow"
```

结果：

- structured output 兼容专项测试：通过
- 非 LLM 回归：`79 passed, 9 deselected`
