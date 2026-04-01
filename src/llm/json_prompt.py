"""structured output / JSON prompt 兼容工具。"""

from __future__ import annotations


def ensure_json_keyword(text: str, suffix: str) -> str:
    """确保 prompt 中显式包含 json/JSON 关键词。"""
    return text if "json" in text.lower() else text + suffix


def build_json_messages(
    system_prompt: str,
    user_message: str,
    *,
    system_suffix: str = "\n\n输出必须是 JSON 对象。",
    user_suffix: str = "\n\n请返回 JSON。",
) -> list[dict[str, str]]:
    """构建带 JSON 兼容保护的 messages。"""
    return [
        {"role": "system", "content": ensure_json_keyword(system_prompt, system_suffix)},
        {"role": "user", "content": ensure_json_keyword(user_message, user_suffix)},
    ]
