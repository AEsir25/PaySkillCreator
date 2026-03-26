"""Tree-sitter 代码结构解析工具 — 提取类、方法、imports 等结构信息

tree-sitter 不可用时自动降级为正则匹配。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tree-sitter 初始化（可选依赖）
# ---------------------------------------------------------------------------

_TS_AVAILABLE = False
_JAVA_LANGUAGE = None

try:
    import tree_sitter
    import tree_sitter_java

    _JAVA_LANGUAGE = tree_sitter.Language(tree_sitter_java.language())
    _TS_AVAILABLE = True
    logger.debug("tree-sitter 初始化成功")
except Exception:
    logger.debug("tree-sitter 不可用，将使用正则降级")


_LANG_MAP: dict[str, object | None] = {
    ".java": _JAVA_LANGUAGE,
}

# ---------------------------------------------------------------------------
# Tree-sitter 解析实现
# ---------------------------------------------------------------------------


def _ts_parse(source: bytes, language: object) -> object | None:
    """使用 tree-sitter 解析源代码，返回根节点。"""
    import tree_sitter
    parser = tree_sitter.Parser(language)
    tree = parser.parse(source)
    return tree.root_node


def _ts_extract_structure(root_node: object, source_lines: list[str]) -> dict:
    """从 tree-sitter AST 提取结构信息。"""
    imports: list[str] = []
    classes: list[dict] = []

    def _walk(node: object, current_class: dict | None = None) -> None:
        ntype = node.type

        if ntype == "import_declaration":
            imports.append(node.text.decode("utf-8").strip())

        elif ntype in ("class_declaration", "interface_declaration", "enum_declaration"):
            name_node = node.child_by_field_name("name")
            cls_name = name_node.text.decode("utf-8") if name_node else "<unknown>"
            cls = {
                "name": cls_name,
                "type": ntype.replace("_declaration", ""),
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "methods": [],
                "fields": [],
            }
            classes.append(cls)
            for child in node.children:
                _walk(child, cls)
            return

        elif ntype == "method_declaration" and current_class is not None:
            name_node = node.child_by_field_name("name")
            method_name = name_node.text.decode("utf-8") if name_node else "<unknown>"
            current_class["methods"].append({
                "name": method_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
            })
            return

        elif ntype == "field_declaration" and current_class is not None:
            decl_text = node.text.decode("utf-8").strip()
            name_match = re.search(r"(\w+)\s*[;=]", decl_text)
            if name_match:
                current_class["fields"].append(name_match.group(1))

        for child in node.children:
            _walk(child, current_class)

    _walk(root_node)
    return {"imports": imports, "classes": classes}


# ---------------------------------------------------------------------------
# 正则降级解析
# ---------------------------------------------------------------------------

_RE_JAVA_IMPORT = re.compile(r"^\s*import\s+(.+?)\s*;", re.MULTILINE)
_RE_JAVA_CLASS = re.compile(
    r"(?:public\s+|abstract\s+|final\s+)*(class|interface|enum)\s+(\w+)", re.MULTILINE
)
_RE_JAVA_METHOD = re.compile(
    r"(?:public|private|protected|static|\s)+\s+[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{",
    re.MULTILINE,
)
_RE_PYTHON_CLASS = re.compile(r"^class\s+(\w+)", re.MULTILINE)
_RE_PYTHON_DEF = re.compile(r"^(?:\s*)def\s+(\w+)\s*\(", re.MULTILINE)
_RE_PYTHON_IMPORT = re.compile(r"^(?:import|from)\s+.+", re.MULTILINE)


def _regex_extract_structure(source: str, suffix: str) -> dict:
    """正则降级提取结构。"""
    imports: list[str] = []
    classes: list[dict] = []

    if suffix == ".java":
        imports = [m.group(0).strip() for m in _RE_JAVA_IMPORT.finditer(source)]
        lines = source.splitlines()
        for m in _RE_JAVA_CLASS.finditer(source):
            cls_type, cls_name = m.group(1), m.group(2)
            line_no = source[: m.start()].count("\n") + 1
            methods = []
            for mm in _RE_JAVA_METHOD.finditer(source):
                methods.append({
                    "name": mm.group(1),
                    "start_line": source[: mm.start()].count("\n") + 1,
                })
            classes.append({
                "name": cls_name,
                "type": cls_type,
                "start_line": line_no,
                "methods": methods,
                "fields": [],
            })
    elif suffix == ".py":
        imports = [m.group(0).strip() for m in _RE_PYTHON_IMPORT.finditer(source)]
        for m in _RE_PYTHON_CLASS.finditer(source):
            line_no = source[: m.start()].count("\n") + 1
            classes.append({
                "name": m.group(1),
                "type": "class",
                "start_line": line_no,
                "methods": [],
                "fields": [],
            })
        for m in _RE_PYTHON_DEF.finditer(source):
            line_no = source[: m.start()].count("\n") + 1
            if classes:
                classes[-1]["methods"].append({"name": m.group(1), "start_line": line_no})
            else:
                classes.append({
                    "name": "<module>",
                    "type": "module",
                    "start_line": 1,
                    "methods": [{"name": m.group(1), "start_line": line_no}],
                    "fields": [],
                })

    return {"imports": imports, "classes": classes}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def parse_file_structure(file_path: str, repo_path: str) -> str:
    """解析代码文件的结构，提取 imports、类、方法、字段信息。

    Args:
        file_path: 文件路径（绝对路径或相对于 repo_path 的相对路径）
        repo_path: 仓库根目录路径
    """
    repo = Path(repo_path).resolve()
    target = Path(file_path)
    if not target.is_absolute():
        target = repo / target
    target = target.resolve()

    if not target.is_file():
        return f"错误: 文件不存在 — {file_path}"

    try:
        source = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"读取失败: {e}"

    suffix = target.suffix
    lang = _LANG_MAP.get(suffix) if _TS_AVAILABLE else None

    if lang is not None:
        root = _ts_parse(source.encode("utf-8"), lang)
        if root:
            structure = _ts_extract_structure(root, source.splitlines())
        else:
            structure = _regex_extract_structure(source, suffix)
    else:
        structure = _regex_extract_structure(source, suffix)

    result = {"file": str(target.relative_to(repo)), **structure}
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def extract_method_body(file_path: str, method_name: str, repo_path: str) -> str:
    """提取指定方法的完整代码体。

    Args:
        file_path: 文件路径
        method_name: 要提取的方法名
        repo_path: 仓库根目录路径
    """
    repo = Path(repo_path).resolve()
    target = Path(file_path)
    if not target.is_absolute():
        target = repo / target
    target = target.resolve()

    if not target.is_file():
        return f"错误: 文件不存在 — {file_path}"

    try:
        source = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"读取失败: {e}"

    suffix = target.suffix
    lang = _LANG_MAP.get(suffix) if _TS_AVAILABLE else None
    lines = source.splitlines()

    if lang is not None:
        root = _ts_parse(source.encode("utf-8"), lang)
        if root:
            found = _ts_find_method(root, method_name)
            if found:
                start, end = found
                selected = lines[start - 1 : end]
                numbered = [f"{start + i:>6}|{l}" for i, l in enumerate(selected)]
                return f"--- {target.relative_to(repo)}:{method_name} (lines {start}-{end}) ---\n" + "\n".join(numbered)

    return _regex_extract_method(source, method_name, str(target.relative_to(repo)), suffix)


def _ts_find_method(root_node: object, method_name: str) -> tuple[int, int] | None:
    """在 AST 中查找指定方法，返回 (start_line, end_line)。"""
    def _walk(node: object) -> tuple[int, int] | None:
        if node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node and name_node.text.decode("utf-8") == method_name:
                return (node.start_point[0] + 1, node.end_point[0] + 1)
        for child in node.children:
            result = _walk(child)
            if result:
                return result
        return None

    return _walk(root_node)


def _regex_extract_method(source: str, method_name: str, rel_path: str, suffix: str) -> str:
    """正则提取方法体（降级方案）。"""
    lines = source.splitlines()

    if suffix == ".java":
        pattern = re.compile(
            rf"(?:public|private|protected|static|\s)+\s+[\w<>\[\],\s]+\s+{re.escape(method_name)}\s*\("
        )
    elif suffix == ".py":
        pattern = re.compile(rf"^\s*def\s+{re.escape(method_name)}\s*\(", re.MULTILINE)
    else:
        pattern = re.compile(rf"\b{re.escape(method_name)}\s*\(")

    match = pattern.search(source)
    if not match:
        return f"未找到方法: {method_name}"

    start_line = source[: match.start()].count("\n")

    if suffix == ".java":
        brace_count = 0
        end_line = start_line
        started = False
        for i in range(start_line, len(lines)):
            for ch in lines[i]:
                if ch == "{":
                    brace_count += 1
                    started = True
                elif ch == "}":
                    brace_count -= 1
            if started and brace_count == 0:
                end_line = i
                break
        else:
            end_line = min(start_line + 50, len(lines) - 1)
    elif suffix == ".py":
        indent = len(lines[start_line]) - len(lines[start_line].lstrip())
        end_line = start_line
        for i in range(start_line + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped == "":
                continue
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            if current_indent <= indent:
                break
            end_line = i
    else:
        end_line = min(start_line + 30, len(lines) - 1)

    selected = lines[start_line : end_line + 1]
    numbered = [f"{start_line + 1 + i:>6}|{l}" for i, l in enumerate(selected)]
    return f"--- {rel_path}:{method_name} (lines {start_line + 1}-{end_line + 1}) ---\n" + "\n".join(numbered)


@tool
def find_method_calls(file_path: str, method_name: str, repo_path: str) -> str:
    """分析指定方法内部调用了哪些其他方法。

    Args:
        file_path: 文件路径
        method_name: 要分析的方法名
        repo_path: 仓库根目录路径
    """
    repo = Path(repo_path).resolve()
    target = Path(file_path)
    if not target.is_absolute():
        target = repo / target
    target = target.resolve()

    if not target.is_file():
        return f"错误: 文件不存在 — {file_path}"

    try:
        source = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"读取失败: {e}"

    suffix = target.suffix
    lang = _LANG_MAP.get(suffix) if _TS_AVAILABLE else None

    if lang is not None:
        root = _ts_parse(source.encode("utf-8"), lang)
        if root:
            method_range = _ts_find_method(root, method_name)
            if method_range:
                start, end = method_range
                method_source = "\n".join(source.splitlines()[start - 1 : end])
                calls = _extract_calls_from_source(method_source)
                return json.dumps({
                    "method": method_name,
                    "file": str(target.relative_to(repo)),
                    "calls": calls,
                }, ensure_ascii=False, indent=2)

    body_text = _regex_extract_method(source, method_name, str(target.relative_to(repo)), suffix)
    if body_text.startswith("未找到"):
        return body_text

    calls = _extract_calls_from_source(body_text)
    return json.dumps({
        "method": method_name,
        "file": str(target.relative_to(repo)),
        "calls": calls,
    }, ensure_ascii=False, indent=2)


_RE_METHOD_CALL = re.compile(r"(?:(\w+)\.)?(\w+)\s*\(")

_NOISE_CALLS = {
    "if", "for", "while", "switch", "catch", "return", "throw",
    "new", "super", "this", "print", "println", "printf",
    "String", "Integer", "Long", "Boolean", "Double", "Float",
    "List", "Map", "Set", "Optional", "Arrays", "Collections",
    "len", "range", "str", "int", "float", "bool", "dict", "list", "tuple", "set",
    "isinstance", "getattr", "setattr", "hasattr", "type",
}


def _extract_calls_from_source(source: str) -> list[str]:
    """从方法体源码中提取方法调用。"""
    calls: list[str] = []
    seen: set[str] = set()
    for m in _RE_METHOD_CALL.finditer(source):
        obj, method = m.group(1), m.group(2)
        if method in _NOISE_CALLS:
            continue
        call = f"{obj}.{method}()" if obj else f"{method}()"
        if call not in seen:
            seen.add(call)
            calls.append(call)
    return calls
