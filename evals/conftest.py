"""评估测试共用 fixture"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="session")
def repo_path() -> str:
    """从环境变量获取目标仓库路径，未设置则跳过。"""
    path = os.getenv("TARGET_REPO_PATH", "")
    if not path or not Path(path).is_dir():
        pytest.skip("TARGET_REPO_PATH 未设置或不存在，跳过需要真实仓库的测试")
    return path


@pytest.fixture(scope="session")
def has_api_key() -> bool:
    """检查是否配置了 LLM API Key。"""
    return bool(os.getenv("OPENAI_API_KEY"))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "llm: 需要真实 LLM API 调用的测试")
    config.addinivalue_line("markers", "slow: 运行较慢的测试")
