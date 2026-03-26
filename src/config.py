from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


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
    settings = Settings()
    return settings
