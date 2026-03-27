"""PaySkillCreator Web — FastAPI + SSE 流式响应"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.config import Settings, get_settings
from src.graph.builder import build_graph
from src.state import VALID_SKILLS

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="PaySkillCreator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class AnalyzeRequest(BaseModel):
    repo_path: str
    query: str
    skill: str | None = None


_NODE_LABELS: dict[str, tuple[str, str]] = {
    "skill_router": ("routing", "正在识别任务类型..."),
    "context_retriever": ("retrieving", "正在检索仓库上下文..."),
    "skill_executor": ("executing", "正在执行 Skill 分析..."),
    "formatter": ("formatting", "正在生成结构化报告..."),
    "skill_spec_generator": ("spec_generating", "正在生成 Skill 规格..."),
    "skill_md_formatter": ("md_rendering", "正在渲染 SKILL.md..."),
}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/", response_class=HTMLResponse)
async def index():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/config")
async def get_config():
    settings = get_settings()
    return {
        "repo_path": settings.target_repo_path,
        "model_name": settings.llm.model_name,
        "max_context_tokens": settings.max_context_tokens,
        "skills": list(VALID_SKILLS),
    }


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    return StreamingResponse(
        _run_analysis(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _run_analysis(req: AnalyzeRequest):
    """同步生成器：逐节点 stream graph 执行，发送 SSE 事件。"""
    settings = get_settings()

    repo_path = req.repo_path or settings.target_repo_path
    if not repo_path or not Path(repo_path).is_dir():
        yield _sse("error", {"message": f"仓库路径无效: {repo_path}"})
        return

    try:
        Settings(
            llm=settings.llm,
            target_repo_path=repo_path,
        ).validate()
    except ValueError as e:
        yield _sse("error", {"message": str(e)})
        return

    initial_state = {
        "repo_path": repo_path,
        "user_query": req.query,
        "requested_skill": req.skill if req.skill in VALID_SKILLS else None,
        "need_review": False,
        "metadata": {},
    }

    graph = build_graph(checkpointer=False)
    t0 = time.time()
    final_state = {}

    try:
        for event in graph.stream(initial_state, stream_mode="updates"):
            for node_name, node_output in event.items():
                final_state.update(node_output)

                label = _NODE_LABELS.get(node_name)
                if not label:
                    continue
                stage, msg = label

                payload: dict = {"stage": stage, "message": msg}

                if node_name == "skill_router":
                    skill_type = node_output.get("skill_type", "")
                    meta = node_output.get("metadata", {})
                    payload["skill_type"] = skill_type
                    payload["router_reason"] = meta.get("router_reason", "")

                yield _sse("status", payload)

        output = final_state.get("formatted_output", "")
        metadata = final_state.get("metadata", {})
        elapsed_ms = int((time.time() - t0) * 1000)
        metadata["total_elapsed_ms"] = elapsed_ms

        yield _sse("result", {
            "formatted_output": output,
            "skill_type": final_state.get("skill_type", ""),
            "metadata": metadata,
        })

    except Exception as e:
        logger.exception("分析执行失败")
        yield _sse("error", {"message": f"分析失败: {e}"})

    yield _sse("done", {})
