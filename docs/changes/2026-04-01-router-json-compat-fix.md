# 2026-04-01 路由 JSON 兼容性修复

## 背景

在部分 OpenAI 兼容 provider 上，使用 `with_structured_output()` 时如果消息内容中没有显式包含 `json/JSON` 字样，会返回如下错误：

```text
'messages' must contain the word 'json' in some form, to use 'response_format' of type 'json_object'
```

该问题会导致 LLM 路由失败，并退回关键词路由。

## 本次修复

- 在 `src/prompts/router.py` 中明确要求路由输出为 JSON
- 在 `src/graph/nodes.py` 的 `_llm_route()` 中补充保护逻辑，确保 system/user message 都包含 JSON 相关指令
- 新增测试 `evals/test_router_structured_output.py`，锁定这类 provider 兼容行为

## 影响

- LLM 路由在 DashScope / 部分兼容 provider 下更稳定
- 不会再因为缺少 `json` 关键词而直接触发 400
- 关键词 fallback 仍然保留，作为兜底机制

## 测试结果

执行：

```bash
.venv/bin/python -m pytest evals/test_router_structured_output.py -q
.venv/bin/python -m pytest evals -q -k "not llm and not slow"
```

结果：

- `test_router_structured_output.py`: 通过
- 非 LLM 回归：`78 passed, 9 deselected`
