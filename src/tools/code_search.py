"""代码搜索工具 — 基于 ripgrep 的仓库代码搜索，支持 grep 降级"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_RG_BIN: str | None = shutil.which("rg")
_GREP_BIN: str | None = shutil.which("grep")

MAX_RESULTS = 30
CONTEXT_LINES = 2


def _run_cmd(cmd: list[str], cwd: str, timeout: int = 30) -> str:
    """执行外部命令并返回 stdout。"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "[搜索超时]"
    except FileNotFoundError:
        return f"[命令未找到: {cmd[0]}]"
    except Exception as e:
        return f"[搜索出错: {e}]"


def _rg_search(
    pattern: str,
    cwd: str,
    file_glob: str | None = None,
    context: int = CONTEXT_LINES,
    max_count: int = MAX_RESULTS,
    extra_args: list[str] | None = None,
) -> str:
    """使用 ripgrep 搜索。"""
    cmd = [
        _RG_BIN or "rg",
        "--no-heading",
        "--line-number",
        f"--max-count={max_count}",
        f"-C{context}",
        "--color=never",
        "--glob=!.venv",
        "--glob=!.git",
        "--glob=!node_modules",
        "--glob=!__pycache__",
        "--glob=!target",
        "--glob=!build",
        "--glob=!.payskill_cache",
    ]
    if file_glob:
        cmd.extend(["--glob", file_glob])
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend([pattern, "."])
    return _run_cmd(cmd, cwd)


def _grep_search(
    pattern: str,
    cwd: str,
    file_glob: str | None = None,
    context: int = CONTEXT_LINES,
    max_count: int = MAX_RESULTS,
) -> str:
    """使用系统 grep 作为降级方案。"""
    cmd = [
        _GREP_BIN or "grep",
        "-rn",
        f"-C{context}",
        f"-m{max_count}",
        "--color=never",
        "--include", file_glob or "*",
    ]
    cmd.extend([
        "--exclude-dir=.git",
        "--exclude-dir=node_modules",
        "--exclude-dir=__pycache__",
        "--exclude-dir=.venv",
        "--exclude-dir=target",
        "--exclude-dir=build",
    ])
    cmd.extend([pattern, "."])
    return _run_cmd(cmd, cwd)


def _do_search(
    pattern: str,
    cwd: str,
    file_glob: str | None = None,
    context: int = CONTEXT_LINES,
    max_count: int = MAX_RESULTS,
    extra_rg_args: list[str] | None = None,
) -> str:
    if _RG_BIN:
        return _rg_search(pattern, cwd, file_glob, context, max_count, extra_rg_args)
    return _grep_search(pattern, cwd, file_glob, context, max_count)


def _format_result(raw: str, label: str) -> str:
    lines = raw.strip().splitlines()
    if not lines or (len(lines) == 1 and not lines[0].strip()):
        return f"[{label}] 未找到匹配结果"
    total = sum(1 for l in lines if l and not l.startswith("--"))
    if total > MAX_RESULTS * 3:
        lines = lines[: MAX_RESULTS * 5]
        lines.append(f"... (结果过多，已截断)")
    return f"[{label}] 共 {total} 行匹配:\n" + "\n".join(lines)


@tool
def search_code(pattern: str, repo_path: str, file_glob: str = "", max_results: int = 20) -> str:
    """在仓库中搜索匹配指定正则模式的代码行，返回文件路径、行号和上下文。

    Args:
        pattern: 搜索的正则表达式模式
        repo_path: 仓库根目录路径
        file_glob: 可选的文件过滤 glob 模式，如 "*.java" 或 "*.py"
        max_results: 最大返回结果数，默认 20
    """
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        return f"错误: 仓库路径不存在 — {repo_path}"
    raw = _do_search(pattern, str(repo), file_glob or None, CONTEXT_LINES, max_results)
    return _format_result(raw, f"search_code: {pattern}")


@tool
def search_symbol(name: str, repo_path: str, symbol_type: str = "any", file_glob: str = "") -> str:
    """搜索类名、方法名或接口名的定义位置。

    Args:
        name: 要搜索的符号名称（类名、方法名等）
        repo_path: 仓库根目录路径
        symbol_type: 符号类型，可选 "class" / "method" / "interface" / "any"，默认 "any"
        file_glob: 可选的文件过滤 glob 模式
    """
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        return f"错误: 仓库路径不存在 — {repo_path}"

    patterns: dict[str, str] = {
        "class": rf"(class|abstract\s+class|enum)\s+{name}\b",
        "interface": rf"interface\s+{name}\b",
        "method": rf"(public|private|protected|static|\s)\s+\w+\s+{name}\s*\(",
        "any": rf"(class|interface|enum|def|function|func)\s+{name}\b|\w+\s+{name}\s*\(",
    }
    pattern = patterns.get(symbol_type, patterns["any"])
    raw = _do_search(pattern, str(repo), file_glob or None, CONTEXT_LINES, MAX_RESULTS)
    return _format_result(raw, f"search_symbol: {name} ({symbol_type})")


@tool
def search_references(name: str, repo_path: str, file_glob: str = "") -> str:
    """搜索某个符号（类名、方法名等）在仓库中的所有引用位置。

    Args:
        name: 要搜索的符号名称
        repo_path: 仓库根目录路径
        file_glob: 可选的文件过滤 glob 模式
    """
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        return f"错误: 仓库路径不存在 — {repo_path}"

    pattern = rf"\b{name}\b"
    raw = _do_search(pattern, str(repo), file_glob or None, 1, MAX_RESULTS)
    return _format_result(raw, f"search_references: {name}")
