from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Provider & Model 注册表
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelDef:
    """单个模型定义。"""
    id: str
    display_name: str
    provider: str
    model_name: str
    description: str = ""


@dataclass(frozen=True)
class ProviderDef:
    """单个 Provider 定义。"""
    id: str
    display_name: str
    api_key_env: str
    base_url_env: str
    default_base_url: str
    models: tuple[ModelDef, ...]


PROVIDERS: tuple[ProviderDef, ...] = (
    ProviderDef(
        id="dashscope",
        display_name="阿里百炼",
        api_key_env="DASHSCOPE_API_KEY",
        base_url_env="DASHSCOPE_BASE_URL",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=(
            ModelDef("qwen-turbo", "Qwen Turbo", "dashscope", "qwen-turbo", "快速经济，适合简单任务"),
            ModelDef("qwen-plus", "Qwen Plus", "dashscope", "qwen-plus", "性价比最高，推荐日常使用"),
            ModelDef("qwen-max", "Qwen Max", "dashscope", "qwen-max", "最强能力，适合复杂分析"),
            ModelDef("qwen-long", "Qwen Long", "dashscope", "qwen-long", "长上下文（100万 tokens）"),
        ),
    ),
    ProviderDef(
        id="minimax",
        display_name="MiniMax",
        api_key_env="MINIMAX_API_KEY",
        base_url_env="MINIMAX_BASE_URL",
        default_base_url="https://api.minimax.chat/v1/text/chatcompletion_v2",
        models=(
            ModelDef("abab6.5s-chat", "ABAB 6.5s", "minimax", "abab6.5s-chat", "高性价比对话模型"),
            ModelDef("abab6.5-chat", "ABAB 6.5", "minimax", "abab6.5-chat", "旗舰对话模型"),
        ),
    ),
    ProviderDef(
        id="openai",
        display_name="OpenAI",
        api_key_env="OPENAI_NATIVE_API_KEY",
        base_url_env="OPENAI_NATIVE_BASE_URL",
        default_base_url="https://api.openai.com/v1",
        models=(
            ModelDef("gpt-4o", "GPT-4o", "openai", "gpt-4o", "多模态旗舰"),
            ModelDef("gpt-4o-mini", "GPT-4o Mini", "openai", "gpt-4o-mini", "经济高效"),
        ),
    ),
)

_PROVIDER_MAP: dict[str, ProviderDef] = {p.id: p for p in PROVIDERS}
_MODEL_MAP: dict[str, tuple[ModelDef, ProviderDef]] = {}
for _p in PROVIDERS:
    for _m in _p.models:
        _MODEL_MAP[_m.id] = (_m, _p)


def _resolve_provider_key(provider: ProviderDef) -> str:
    """获取 Provider 的 API Key，兼容 OPENAI_API_KEY 作为 DashScope 降级。"""
    key = os.getenv(provider.api_key_env, "")
    if not key and provider.id == "dashscope":
        key = os.getenv("OPENAI_API_KEY", "")
    return key


def _resolve_provider_base_url(provider: ProviderDef) -> str:
    url = os.getenv(provider.base_url_env, "")
    if not url and provider.id == "dashscope":
        url = os.getenv("OPENAI_BASE_URL", "")
    return url or provider.default_base_url


def get_available_models() -> list[dict]:
    """返回当前可用的模型列表（仅包含已配置 API Key 的 Provider）。"""
    result: list[dict] = []
    for prov in PROVIDERS:
        if not _resolve_provider_key(prov):
            continue
        for m in prov.models:
            result.append({
                "id": m.id,
                "name": m.display_name,
                "provider": prov.display_name,
                "provider_id": prov.id,
                "description": m.description,
            })
    return result


def get_default_model_id() -> str:
    """返回默认模型 ID，优先读 MODEL_NAME 环境变量。"""
    env_model = os.getenv("MODEL_NAME", "")
    if env_model and env_model in _MODEL_MAP:
        return env_model
    available = get_available_models()
    return available[0]["id"] if available else "qwen-plus"


# ---------------------------------------------------------------------------
# LLMConfig & Settings（向后兼容）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMConfig:
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "gpt-4o"))


@dataclass(frozen=True)
class Settings:
    llm: LLMConfig = field(default_factory=LLMConfig)
    target_repo_path: str = field(
        default_factory=lambda: os.getenv("TARGET_REPO_PATH", "")
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    max_context_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
    )
    need_human_review: bool = field(
        default_factory=lambda: os.getenv("NEED_HUMAN_REVIEW", "false").lower() == "true"
    )

    def validate(self) -> None:
        if not self.llm.api_key:
            raise ValueError("OPENAI_API_KEY is required. Set it in .env or environment.")
        if not self.target_repo_path:
            raise ValueError("TARGET_REPO_PATH is required. Set it in .env or environment.")
        repo = Path(self.target_repo_path)
        if not repo.is_dir():
            raise ValueError(f"TARGET_REPO_PATH does not exist: {self.target_repo_path}")


def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# get_llm — 支持动态模型选择
# ---------------------------------------------------------------------------

def get_llm(settings: Settings | None = None, model_id: str | None = None):
    """创建 ChatOpenAI 实例。

    Args:
        settings: 全局配置（向后兼容，用于无 model_id 时 fallback）
        model_id: 模型 ID（如 "qwen-plus", "abab6.5s-chat"），
                  传入时按 Provider 注册表查找凭据。
    """
    from langchain_openai import ChatOpenAI

    if model_id and model_id in _MODEL_MAP:
        model_def, provider_def = _MODEL_MAP[model_id]
        api_key = _resolve_provider_key(provider_def)
        base_url = _resolve_provider_base_url(provider_def)
        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_def.model_name,
            temperature=0,
        )

    s = settings or get_settings()
    return ChatOpenAI(
        api_key=s.llm.api_key,
        base_url=s.llm.base_url,
        model=s.llm.model_name,
        temperature=0,
    )
