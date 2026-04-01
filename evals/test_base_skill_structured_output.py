"""BaseSkill structured output 兼容性测试"""

from __future__ import annotations

from pydantic import BaseModel

from src.skills.base import BaseSkill


class _OutputSchema(BaseModel):
    value: str


class _DummySkill(BaseSkill):
    name = "dummy"

    def execute(self, query: str, context):  # type: ignore[no-untyped-def]
        return {}


def test_base_skill_structured_messages_include_json() -> None:
    captured: dict[str, object] = {}

    class _FakeStructuredLLM:
        def invoke(self, messages):  # type: ignore[no-untyped-def]
            captured["messages"] = messages
            return _OutputSchema(value="ok")

    class _FakeLLM:
        def with_structured_output(self, schema):  # type: ignore[no-untyped-def]
            return _FakeStructuredLLM()

    skill = _DummySkill(llm=_FakeLLM(), repo_path="/tmp/repo")
    result = skill._call_llm_structured(
        system_prompt="你是一个分析助手。",
        user_message="请输出结果",
        output_schema=_OutputSchema,
    )

    assert result.value == "ok"
    messages = captured["messages"]
    assert any("json" in message["content"].lower() for message in messages)
