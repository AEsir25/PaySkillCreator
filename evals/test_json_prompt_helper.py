"""JSON prompt helper 测试"""

from __future__ import annotations

from src.llm.json_prompt import build_json_messages, ensure_json_keyword


def test_ensure_json_keyword_appends_suffix_when_missing() -> None:
    result = ensure_json_keyword("你是一个助手。", "\n请返回 JSON。")
    assert "json" in result.lower()


def test_build_json_messages_protects_both_roles() -> None:
    messages = build_json_messages("系统提示", "用户问题")
    assert len(messages) == 2
    assert all("json" in message["content"].lower() for message in messages)
