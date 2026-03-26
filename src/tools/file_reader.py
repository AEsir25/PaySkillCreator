"""文件读取工具 — 提供文件内容读取和目录结构扫描能力"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_KEY_FILENAMES: set[str] = {
    "README.md",
    "README.rst",
    "README.txt",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env.example",
}

_BINARY_EXTENSIONS: set[str] = {
    ".class", ".jar", ".war", ".ear",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".zip", ".gz", ".tar", ".rar",
    ".exe", ".dll", ".so", ".dylib",
    ".pdf", ".doc", ".docx",
    ".pyc", ".pyo",
    ".woff", ".woff2", ".ttf", ".eot",
}

MAX_FILE_LINES = 500
MAX_DIR_ENTRIES = 200


def _validate_path(file_path: str, repo_path: str) -> Path:
    """校验路径安全性，防止路径穿越。"""
    repo = Path(repo_path).resolve()
    target = Path(file_path).resolve()
    if not str(target).startswith(str(repo)):
        raise ValueError(f"路径不在仓库范围内: {file_path}")
    return target


@tool
def read_file(file_path: str, repo_path: str, start_line: int = 1, end_line: int = 0) -> str:
    """读取指定文件的内容。支持指定行范围。

    Args:
        file_path: 要读取的文件路径（绝对路径或相对于 repo_path 的相对路径）
        repo_path: 仓库根目录路径
        start_line: 起始行号（从 1 开始），默认 1
        end_line: 结束行号（包含），0 表示读到文件末尾
    """
    repo = Path(repo_path).resolve()
    target = Path(file_path)
    if not target.is_absolute():
        target = repo / target
    target = _validate_path(str(target), repo_path)

    if not target.is_file():
        return f"错误: 文件不存在 — {file_path}"

    if target.suffix in _BINARY_EXTENSIONS:
        return f"跳过二进制文件: {file_path}"

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"读取失败: {e}"

    lines = text.splitlines()
    total = len(lines)

    start = max(1, start_line)
    end = end_line if end_line > 0 else total
    end = min(end, total)

    selected = lines[start - 1 : end]
    if len(selected) > MAX_FILE_LINES:
        selected = selected[:MAX_FILE_LINES]
        truncated = True
    else:
        truncated = False

    numbered = [f"{start + i:>6}|{line}" for i, line in enumerate(selected)]
    header = f"--- {target.relative_to(repo)} ({total} lines, showing {start}-{start + len(selected) - 1}) ---"
    if truncated:
        header += f" [截断至 {MAX_FILE_LINES} 行]"

    return header + "\n" + "\n".join(numbered)


@tool
def list_directory(dir_path: str, repo_path: str, max_depth: int = 2) -> str:
    """递归列出目录结构。

    Args:
        dir_path: 目录路径（绝对路径或相对于 repo_path 的相对路径）
        repo_path: 仓库根目录路径
        max_depth: 最大递归深度，默认 2
    """
    repo = Path(repo_path).resolve()
    target = Path(dir_path)
    if not target.is_absolute():
        target = repo / target
    target = _validate_path(str(target), repo_path)

    if not target.is_dir():
        return f"错误: 目录不存在 — {dir_path}"

    lines: list[str] = []
    count = 0
    _SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".idea", ".cursor", "build", "target", ".gradle"}

    def _walk(p: Path, depth: int, prefix: str) -> None:
        nonlocal count
        if depth > max_depth or count >= MAX_DIR_ENTRIES:
            return

        try:
            entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") and entry.name in _SKIP_DIRS:
                continue
            if entry.name in _SKIP_DIRS:
                continue
            count += 1
            if count > MAX_DIR_ENTRIES:
                lines.append(f"{prefix}... (截断，超过 {MAX_DIR_ENTRIES} 条)")
                return

            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                _walk(entry, depth + 1, prefix + "  ")
            else:
                lines.append(f"{prefix}{entry.name}")

    rel = target.relative_to(repo)
    lines.append(f"{rel}/")
    _walk(target, 1, "  ")

    return "\n".join(lines)


@tool
def read_key_files(repo_path: str) -> str:
    """自动识别并读取仓库中的关键文件（README、构建配置等），返回摘要内容。

    Args:
        repo_path: 仓库根目录路径
    """
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        return f"错误: 仓库路径不存在 — {repo_path}"

    found: list[str] = []
    for item in sorted(repo.iterdir()):
        if item.name in _KEY_FILENAMES and item.is_file():
            try:
                text = item.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = text.splitlines()
            preview = lines[:80]
            truncated = len(lines) > 80
            header = f"=== {item.name} ({len(lines)} lines) ==="
            content = "\n".join(preview)
            if truncated:
                content += f"\n... (截断，共 {len(lines)} 行)"
            found.append(f"{header}\n{content}")

    if not found:
        return "未找到关键文件 (README, pom.xml, package.json 等)"

    return "\n\n".join(found)
