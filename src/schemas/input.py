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
