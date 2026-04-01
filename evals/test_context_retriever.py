"""context_retriever 结构化输出测试"""

from __future__ import annotations

from pathlib import Path

import src.graph.nodes as nodes
from src.graph.nodes import context_retriever
from src.schemas.input import RetrievedContext


def test_context_retriever_repo_background_returns_structured_context(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")

    result = context_retriever({
        "skill_type": "repo_background",
        "repo_path": str(tmp_path),
        "user_query": "介绍一下这个仓库",
    })

    retrieved = result["retrieved_context"]
    assert isinstance(retrieved, RetrievedContext)
    assert "README.md" in retrieved.key_files_content
    assert "src/" in retrieved.directory_structure
    assert retrieved.combined_context


def test_context_retriever_plan_suggestion_keeps_search_buckets(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    (tmp_path / "payment_service.py").write_text(
        "def add_refund_feature():\n    return 'refund'\n",
        encoding="utf-8",
    )

    result = context_retriever({
        "skill_type": "plan_suggestion",
        "repo_path": str(tmp_path),
        "user_query": "如何添加 refund 功能",
    })

    retrieved = result["retrieved_context"]
    assert isinstance(retrieved, RetrievedContext)
    assert retrieved.directory_structure
    assert retrieved.key_files_content
    assert isinstance(retrieved.keyword_search_hits, list)
    assert isinstance(retrieved.semantic_search_hits, list)
    assert retrieved.combined_context


def test_context_retriever_deduplicates_keyword_searches(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    search_calls: list[str] = []

    monkeypatch.setattr(nodes, "_extract_search_terms", lambda query: ["RefundService", "refundservice", "RefundService"])

    original_cached_tool_text = nodes._cached_tool_text

    def fake_cached_tool_text(cache, tool_name: str, cache_key: str, loader):  # type: ignore[no-untyped-def]
        if tool_name == "search_code":
            search_calls.append(cache_key)
            return f"[search_code: {cache_key}]"
        if tool_name == "semantic_search":
            return "未找到可索引的代码文件"
        return original_cached_tool_text(cache, tool_name, cache_key, loader)

    monkeypatch.setattr(nodes, "_cached_tool_text", fake_cached_tool_text)

    result = context_retriever({
        "skill_type": "plan_suggestion",
        "repo_path": str(tmp_path),
        "user_query": "如何添加退款功能",
    })

    retrieved = result["retrieved_context"]
    assert search_calls == ["RefundService"]
    assert retrieved.keyword_search_hits == ["[search_code: RefundService]"]
