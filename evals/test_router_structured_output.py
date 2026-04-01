"""路由 structured output 兼容性测试"""

from __future__ import annotations

from src.graph.nodes import _llm_route


def test_llm_route_messages_include_json(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeStructuredLLM:
        def invoke(self, messages):  # type: ignore[no-untyped-def]
            captured["messages"] = messages
            class _Result:
                skill_type = "repo_background"
                reason = "test"
            return _Result()

    class _FakeLLM:
        def with_structured_output(self, schema):  # type: ignore[no-untyped-def]
            return _FakeStructuredLLM()

    monkeypatch.setattr("src.config.get_llm", lambda model_id=None: _FakeLLM())

    skill, reason = _llm_route("介绍一下这个仓库", model_id="qwen-plus")

    messages = captured["messages"]
    assert skill == "repo_background"
    assert reason == "test"
    assert any("json" in message["content"].lower() for message in messages)
