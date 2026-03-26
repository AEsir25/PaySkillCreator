"""向量语义检索工具 — 基于 FAISS 的仓库代码语义搜索

采用懒加载策略：首次搜索时建索引，后续复用。
索引缓存在仓库下的 .payskill_cache/ 目录。
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_CODE_EXTENSIONS: set[str] = {
    ".java", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".kt", ".scala", ".groovy",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".xml", ".yaml", ".yml", ".json", ".toml",
    ".properties", ".sql", ".sh", ".bash",
    ".md", ".txt", ".rst",
}

_SKIP_DIRS: set[str] = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".idea", ".cursor", "build", "target", ".gradle",
    "dist", ".payskill_cache",
}

MAX_LINES_PER_CHUNK = 200
MAX_CHUNKS = 2000


class _IndexCache:
    """全局索引缓存，避免重复构建。"""

    def __init__(self) -> None:
        self.index = None
        self.chunks: list[dict] = []
        self.repo_hash: str = ""

    def is_valid(self, repo_path: str) -> bool:
        return self.index is not None and self.repo_hash == _repo_hash(repo_path)


_cache = _IndexCache()


def _repo_hash(repo_path: str) -> str:
    """基于仓库路径生成简单哈希。"""
    return hashlib.md5(repo_path.encode()).hexdigest()[:12]


def _collect_chunks(repo_path: str) -> list[dict]:
    """收集仓库中所有代码文件，按文件切片。"""
    repo = Path(repo_path).resolve()
    chunks: list[dict] = []

    for fpath in sorted(repo.rglob("*")):
        if len(chunks) >= MAX_CHUNKS:
            break
        if not fpath.is_file():
            continue
        if fpath.suffix not in _CODE_EXTENSIONS:
            continue
        if any(skip in fpath.parts for skip in _SKIP_DIRS):
            continue

        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = text.splitlines()
        rel = str(fpath.relative_to(repo))

        for i in range(0, len(lines), MAX_LINES_PER_CHUNK):
            chunk_lines = lines[i : i + MAX_LINES_PER_CHUNK]
            content = "\n".join(chunk_lines)
            if not content.strip():
                continue
            chunks.append({
                "file": rel,
                "start_line": i + 1,
                "end_line": i + len(chunk_lines),
                "content": content,
            })
            if len(chunks) >= MAX_CHUNKS:
                break

    logger.info("收集到 %d 个代码片段", len(chunks))
    return chunks


def _build_faiss_index(chunks: list[dict], repo_path: str) -> object | None:
    """构建 FAISS 索引。使用简单的 TF-IDF 向量化（不依赖 OpenAI Embedding）。"""
    try:
        import faiss
        import numpy as np
    except ImportError:
        logger.warning("faiss 未安装，语义检索不可用")
        return None

    if not chunks:
        return None

    vocab = _build_vocab([c["content"] for c in chunks])
    vectors = np.array(
        [_tfidf_vector(c["content"], vocab) for c in chunks],
        dtype=np.float32,
    )

    faiss.normalize_L2(vectors)

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    _cache.index = index
    _cache.chunks = chunks
    _cache.repo_hash = _repo_hash(repo_path)
    _cache._vocab = vocab

    cache_dir = Path(repo_path) / ".payskill_cache"
    cache_dir.mkdir(exist_ok=True)
    try:
        faiss.write_index(index, str(cache_dir / "code.faiss"))
        with open(cache_dir / "chunks.pkl", "wb") as f:
            pickle.dump(chunks, f)
        with open(cache_dir / "vocab.pkl", "wb") as f:
            pickle.dump(vocab, f)
        logger.info("索引已缓存到 %s", cache_dir)
    except Exception as e:
        logger.warning("索引缓存失败: %s", e)

    return index


def _load_cached_index(repo_path: str) -> bool:
    """尝试从缓存加载索引。"""
    cache_dir = Path(repo_path) / ".payskill_cache"
    idx_path = cache_dir / "code.faiss"
    chunks_path = cache_dir / "chunks.pkl"
    vocab_path = cache_dir / "vocab.pkl"

    if not all(p.exists() for p in (idx_path, chunks_path, vocab_path)):
        return False

    try:
        import faiss

        _cache.index = faiss.read_index(str(idx_path))
        with open(chunks_path, "rb") as f:
            _cache.chunks = pickle.load(f)
        with open(vocab_path, "rb") as f:
            _cache._vocab = pickle.load(f)
        _cache.repo_hash = _repo_hash(repo_path)
        logger.info("从缓存加载索引: %d chunks", len(_cache.chunks))
        return True
    except Exception as e:
        logger.warning("缓存加载失败: %s", e)
        return False


# ---------------------------------------------------------------------------
# 简易 TF-IDF（避免依赖 OpenAI Embedding API 和 sklearn）
# ---------------------------------------------------------------------------

import math
import re as _re
from collections import Counter

_TOKEN_RE = _re.compile(r"[a-zA-Z_]\w{2,}")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _build_vocab(docs: list[str], max_vocab: int = 5000) -> dict[str, int]:
    df: Counter = Counter()
    for doc in docs:
        df.update(set(_tokenize(doc)))
    most_common = df.most_common(max_vocab)
    return {word: idx for idx, (word, _) in enumerate(most_common)}


def _tfidf_vector(text: str, vocab: dict[str, int]) -> list[float]:
    import numpy as np

    tokens = _tokenize(text)
    tf = Counter(tokens)
    vec = np.zeros(len(vocab), dtype=np.float32)
    for word, count in tf.items():
        if word in vocab:
            vec[vocab[word]] = count
    return vec.tolist()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def build_index(repo_path: str) -> str:
    """对仓库代码建立语义检索索引。首次调用会扫描仓库并构建 FAISS 索引。

    Args:
        repo_path: 仓库根目录路径
    """
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        return f"错误: 仓库路径不存在 — {repo_path}"

    if _cache.is_valid(str(repo)):
        return f"索引已存在: {len(_cache.chunks)} 个代码片段"

    if _load_cached_index(str(repo)):
        return f"从缓存加载索引: {len(_cache.chunks)} 个代码片段"

    chunks = _collect_chunks(str(repo))
    if not chunks:
        return "未找到可索引的代码文件"

    index = _build_faiss_index(chunks, str(repo))
    if index is None:
        return "索引构建失败 (faiss 不可用)"

    return f"索引构建完成: {len(chunks)} 个代码片段, 维度 {index.d}"


@tool
def semantic_search(query: str, repo_path: str, top_k: int = 5) -> str:
    """语义搜索仓库中与查询最相关的代码片段。

    Args:
        query: 搜索查询文本
        repo_path: 仓库根目录路径
        top_k: 返回的最相关结果数，默认 5
    """
    import numpy as np

    repo = Path(repo_path).resolve()

    if not _cache.is_valid(str(repo)):
        if not _load_cached_index(str(repo)):
            chunks = _collect_chunks(str(repo))
            if not chunks:
                return "未找到可索引的代码文件"
            index = _build_faiss_index(chunks, str(repo))
            if index is None:
                return "索引不可用 (faiss 未安装)"

    import faiss

    vocab = getattr(_cache, "_vocab", {})
    query_vec = np.array([_tfidf_vector(query, vocab)], dtype=np.float32)
    faiss.normalize_L2(query_vec)

    k = min(top_k, len(_cache.chunks))
    distances, indices = _cache.index.search(query_vec, k)

    results: list[str] = []
    for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx < 0:
            continue
        chunk = _cache.chunks[idx]
        preview_lines = chunk["content"].splitlines()[:15]
        preview = "\n".join(preview_lines)
        results.append(
            f"--- [{i+1}] {chunk['file']} (lines {chunk['start_line']}-{chunk['end_line']}, score={dist:.3f}) ---\n{preview}"
        )

    if not results:
        return "未找到相关结果"

    return "\n\n".join(results)
