from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.config import Settings, get_available_models, get_default_model_id, get_settings
from src.graph.builder import build_graph

app = typer.Typer(
    name="payskill",
    help="PaySkillCreator - 面向单仓库的分析型 Agent，可生成 SKILL.md",
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(name)s | %(message)s",
    )
    if verbose:
        for name in ("markdown_it", "httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)


def _resolve_settings(
    repo_path: str | None, review: bool = False
) -> Settings:
    settings = get_settings()
    if repo_path:
        settings = Settings(
            llm=settings.llm,
            target_repo_path=repo_path,
            log_level=settings.log_level,
            max_context_tokens=settings.max_context_tokens,
            need_human_review=review or settings.need_human_review,
        )
    return settings


@app.command()
def run(
    query: str = typer.Argument(..., help="用户问题或任务描述"),
    repo_path: Optional[str] = typer.Option(
        None, "--repo", "-r", help="目标仓库路径（覆盖 .env 配置）"
    ),
    skill: Optional[str] = typer.Option(
        None,
        "--skill",
        "-s",
        help="指定 Skill 类型: repo_background / chain_analysis / plan_suggestion / generate_skill",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="指定模型 ID（如 qwen-plus, qwen-max, abab6.5s-chat）",
    ),
    review: bool = typer.Option(False, "--review", help="启用人工审核"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="启用详细日志"),
) -> None:
    """执行 Skill 分析任务"""
    _setup_logging(verbose)
    settings = _resolve_settings(repo_path, review)

    try:
        settings.validate()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        raise typer.Exit(code=1)

    model_id = model or get_default_model_id()

    console.print(
        Panel(
            f"[bold]仓库:[/bold] {settings.target_repo_path}\n"
            f"[bold]问题:[/bold] {query}\n"
            f"[bold]Skill:[/bold] {skill or '自动路由'}\n"
            f"[bold]模型:[/bold] {model_id}",
            title="PaySkillCreator",
            border_style="blue",
        )
    )

    need_review = review or settings.need_human_review
    initial_state = {
        "repo_path": settings.target_repo_path,
        "user_query": query,
        "requested_skill": skill,
        "model_id": model_id,
        "need_review": need_review,
        "metadata": {},
    }

    console.print("[dim]正在构建分析工作流...[/dim]")
    compiled_graph = build_graph(checkpointer=need_review)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}} if need_review else {}

    console.print("[dim]正在执行分析...[/dim]\n")
    final_state = compiled_graph.invoke(initial_state, config=config)

    output = final_state.get("formatted_output", "")
    if output:
        console.print(Markdown(output))
    else:
        console.print("[yellow]未产生输出结果。[/yellow]")

    skill_used = final_state.get("skill_type", "unknown")
    metadata = final_state.get("metadata", {})
    elapsed = metadata.get("skill_elapsed_ms", "?")
    console.print(f"\n[dim]Skill: {skill_used} | 耗时: {elapsed}ms | 审核: {'是' if need_review else '否'}[/dim]")


@app.command(name="generate-skill")
def generate_skill(
    query: str = typer.Argument(..., help="Skill 需求描述，例如 '为这个仓库生成代码链路追踪 Skill'"),
    repo_path: Optional[str] = typer.Option(
        None, "--repo", "-r", help="目标仓库路径（覆盖 .env 配置）"
    ),
    output_path: Optional[str] = typer.Option(
        None, "--output", "-o", help="SKILL.md 输出路径（默认输出到终端）"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="指定模型 ID（如 qwen-plus, qwen-max, abab6.5s-chat）",
    ),
    review: bool = typer.Option(False, "--review", help="启用人工审核"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="启用详细日志"),
) -> None:
    """生成 SKILL.md 文件 — 将仓库理解沉淀为可复用的 Skill 定义"""
    _setup_logging(verbose)
    settings = _resolve_settings(repo_path, review)

    try:
        settings.validate()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        raise typer.Exit(code=1)

    model_id = model or get_default_model_id()

    console.print(
        Panel(
            f"[bold]仓库:[/bold] {settings.target_repo_path}\n"
            f"[bold]需求:[/bold] {query}\n"
            f"[bold]模式:[/bold] SKILL.md 生成\n"
            f"[bold]模型:[/bold] {model_id}",
            title="PaySkillCreator — Generate SKILL.md",
            border_style="magenta",
        )
    )

    need_review = review or settings.need_human_review
    initial_state = {
        "repo_path": settings.target_repo_path,
        "user_query": query,
        "requested_skill": "generate_skill",
        "model_id": model_id,
        "need_review": need_review,
        "metadata": {},
    }

    console.print("[dim]正在构建生成工作流...[/dim]")
    compiled_graph = build_graph(checkpointer=need_review)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}} if need_review else {}

    console.print("[dim]正在分析仓库并生成 SKILL.md...[/dim]\n")
    final_state = compiled_graph.invoke(initial_state, config=config)

    output = final_state.get("formatted_output", "")
    if not output:
        console.print("[yellow]未产生输出结果。[/yellow]")
        raise typer.Exit(code=1)

    if output_path:
        out = Path(output_path)
        out.write_text(output, encoding="utf-8")
        console.print(f"[green]SKILL.md 已写入: {out.resolve()}[/green]")
    else:
        console.print(Markdown(output))

    metadata = final_state.get("metadata", {})
    elapsed = metadata.get("skill_elapsed_ms", "?")
    console.print(f"\n[dim]模式: generate_skill | 耗时: {elapsed}ms[/dim]")


@app.command()
def info() -> None:
    """显示当前配置信息"""
    settings = get_settings()
    models = get_available_models()
    default_model = get_default_model_id()

    model_lines: list[str] = []
    for m in models:
        marker = " [green]← 默认[/green]" if m["id"] == default_model else ""
        model_lines.append(f"  {m['id']:20s}  {m['provider']:10s}  {m['description']}{marker}")

    models_text = "\n".join(model_lines) if model_lines else "  (无可用模型，请在 .env 中配置 API Key)"

    console.print(
        Panel(
            f"[bold]目标仓库:[/bold] {settings.target_repo_path or '(未配置)'}\n"
            f"[bold]默认模型:[/bold] {default_model}\n"
            f"[bold]最大上下文 Tokens:[/bold] {settings.max_context_tokens}\n"
            f"[bold]人工审核:[/bold] {'启用' if settings.need_human_review else '关闭'}\n\n"
            f"[bold]可用模型:[/bold]\n{models_text}",
            title="当前配置",
            border_style="green",
        )
    )


if __name__ == "__main__":
    app()
