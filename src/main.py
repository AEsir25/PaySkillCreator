from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.config import get_settings

app = typer.Typer(
    name="payskill",
    help="PaySkillCreator - 面向单仓库的分析型 Agent",
)
console = Console()


@app.command()
def run(
    query: str = typer.Argument(..., help="用户问题或任务描述"),
    repo_path: Optional[str] = typer.Option(None, "--repo", "-r", help="目标仓库路径（覆盖 .env 配置）"),
    skill: Optional[str] = typer.Option(
        None,
        "--skill",
        "-s",
        help="指定 Skill 类型: repo_background / chain_analysis / plan_suggestion",
    ),
    review: bool = typer.Option(False, "--review", help="启用人工审核"),
) -> None:
    """执行 Skill 分析任务"""
    settings = get_settings()

    if repo_path:
        settings = Settings(
            llm=settings.llm,
            target_repo_path=repo_path,
            log_level=settings.log_level,
            max_context_tokens=settings.max_context_tokens,
            need_human_review=review or settings.need_human_review,
        )

    try:
        settings.validate()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold]仓库:[/bold] {settings.target_repo_path}\n"
            f"[bold]问题:[/bold] {query}\n"
            f"[bold]Skill:[/bold] {skill or '自动路由'}\n"
            f"[bold]模型:[/bold] {settings.llm.model_name}",
            title="PaySkillCreator",
            border_style="blue",
        )
    )

    # TODO: 阶段 1 实现 - 构建并调用 LangGraph StateGraph
    console.print("[yellow]Graph 尚未实现，将在阶段 1 中完成。[/yellow]")


@app.command()
def info() -> None:
    """显示当前配置信息"""
    settings = get_settings()
    console.print(
        Panel(
            f"[bold]目标仓库:[/bold] {settings.target_repo_path or '(未配置)'}\n"
            f"[bold]模型:[/bold] {settings.llm.model_name}\n"
            f"[bold]API Base:[/bold] {settings.llm.base_url}\n"
            f"[bold]最大上下文 Tokens:[/bold] {settings.max_context_tokens}\n"
            f"[bold]人工审核:[/bold] {'启用' if settings.need_human_review else '关闭'}",
            title="当前配置",
            border_style="green",
        )
    )


if __name__ == "__main__":
    app()
