"""Web server 结果透传测试"""

from __future__ import annotations

import json

from web.server import AnalyzeRequest, _run_analysis


def test_run_analysis_result_contains_diagrams(monkeypatch, tmp_path) -> None:
    class _FakeGraph:
        def stream(self, initial_state, stream_mode="updates"):  # type: ignore[no-untyped-def]
            yield {"skill_router": {"skill_type": "chain_analysis", "metadata": {"router_reason": "test"}}}
            yield {
                "skill_executor": {
                    "skill_result": {
                        "diagrams": [
                            {
                                "graph_type": "business_overview",
                                "title": "支付流程概览",
                                "summary": "展示支付主链路",
                                "nodes": [],
                                "edges": [],
                                "annotations": [],
                                "mermaid_fallback": "flowchart TD\n    A-->B",
                            }
                        ]
                    }
                }
            }
            yield {
                "formatter": {
                    "formatted_output": "# 代码逻辑链路分析",
                    "metadata": {},
                }
            }

    monkeypatch.setattr("web.server.build_graph", lambda checkpointer=False: _FakeGraph())

    req = AnalyzeRequest(
        repo_path=str(tmp_path),
        query="分析支付流程",
        skill="chain_analysis",
        model=None,
    )

    events = list(_run_analysis(req))
    result_event = next(event for event in events if event.startswith("event: result"))
    payload = json.loads(result_event.split("data: ", 1)[1])

    assert payload["diagrams"]
    assert payload["diagrams"][0]["graph_type"] == "business_overview"
