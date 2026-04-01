"""输入 Schema 定义"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskInput(BaseModel):
    """用户任务输入"""

    repo_path: str = Field(..., description="目标仓库路径")
    query: str = Field(..., description="用户问题或任务描述")
    skill_type: str | None = Field(
        default=None,
        description="指定 Skill 类型，为空时自动路由",
    )
    need_review: bool = Field(default=False, description="是否需要人工审核")


class RetrievedContext(BaseModel):
    """Graph 预检索得到的结构化上下文。"""

    directory_structure: str = Field(default="", description="仓库目录结构")
    key_files_content: str = Field(default="", description="关键文件内容")
    keyword_search_hits: list[str] = Field(default_factory=list, description="关键词检索命中")
    semantic_search_hits: list[str] = Field(default_factory=list, description="语义检索命中")
    combined_context: list[str] = Field(default_factory=list, description="按 token 截断后的上下文片段")
