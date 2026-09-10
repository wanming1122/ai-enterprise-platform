"""长期记忆管理的请求体模型。"""
from pydantic import BaseModel, Field


class AIMemoryUpdate(BaseModel):
    """编辑记忆内容（≤300 字，重新向量化）。"""

    content: str = Field(min_length=1, max_length=300, description="记忆新内容")
