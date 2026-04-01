"""Skill 对结构化上下文的消费测试"""

from __future__ import annotations

from types import SimpleNamespace

from src.schemas.input import RetrievedContext
from src.skills.plan_suggestion import PlanSuggestionSkill
from src.skills.repo_background import RepoBackgroundSkill


class _DummyLLM:
    pass


def test_repo_background_uses_context_payload(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_call(self, system_prompt: str, user_message: str, output_schema):  # type: ignore[no-untyped-def]
        captured["user_message"] = user_message
        return SimpleNamespace(model_dump=lambda: {
            "overview": "demo",
            "core_modules": [],
            "key_directories": [],
            "entry_points": [],
            "config_extension_points": [],
        }, core_modules=[])

    monkeypatch.setattr(RepoBackgroundSkill, "_call_llm_structured", fake_call)

    skill = RepoBackgroundSkill(llm=_DummyLLM(), repo_path="/tmp/repo")
    context = RetrievedContext(
        directory_structure="repo/\n  src/",
        key_files_content="=== README.md ===\nDemo repo",
    )
    skill.execute("介绍这个仓库", context)

    assert "repo/\n  src/" in captured["user_message"]
    assert "Demo repo" in captured["user_message"]


def test_plan_suggestion_uses_pre_retrieved_hits(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_call(self, system_prompt: str, user_message: str, output_schema):  # type: ignore[no-untyped-def]
        captured["user_message"] = user_message
        return SimpleNamespace(model_dump=lambda: {
            "requirement_understanding": "demo",
            "candidate_changes": ["a"],
            "recommended_path": "b",
            "impact_scope": [],
            "risk_analysis": [],
            "test_suggestions": [],
        }, candidate_changes=["a"])

    monkeypatch.setattr(PlanSuggestionSkill, "_call_llm_structured", fake_call)

    skill = PlanSuggestionSkill(llm=_DummyLLM(), repo_path="/tmp/repo")
    context = RetrievedContext(
        directory_structure="repo/\n  app/",
        key_files_content="=== README.md ===\nPayment repo",
        keyword_search_hits=["[search_code: refund]\napp/service.py:10:def refund()"],
        semantic_search_hits=["payment_service.py lines 1-20"],
    )
    skill.execute("添加退款功能", context)

    assert "app/service.py:10:def refund()" in captured["user_message"]
    assert "payment_service.py lines 1-20" in captured["user_message"]
    assert "Payment repo" in captured["user_message"]
