"""配置收敛测试"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings, get_available_models, get_default_model_id, get_llm


def test_default_model_uses_env_when_valid(monkeypatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "qwen-max")

    assert get_default_model_id() == "qwen-max"


def test_available_models_filtered_by_provider_keys(monkeypatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_NATIVE_API_KEY", raising=False)
    monkeypatch.setenv("MINIMAX_API_KEY", "mini-key")

    models = get_available_models()
    assert models
    assert all(model["provider_id"] == "minimax" for model in models)


def test_settings_validate_requires_any_provider_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_NATIVE_API_KEY", raising=False)

    settings = Settings(target_repo_path=str(tmp_path))
    with pytest.raises(ValueError, match="未找到任何 LLM API Key"):
        settings.validate()


def test_get_llm_uses_provider_registry(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class DummyChatOpenAI:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)

    monkeypatch.setenv("DASHSCOPE_API_KEY", "dash-key")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr("langchain_openai.ChatOpenAI", DummyChatOpenAI)

    get_llm("qwen-plus")

    assert captured["api_key"] == "dash-key"
    assert captured["base_url"] == "https://example.test/v1"
    assert captured["model"] == "qwen-plus"
