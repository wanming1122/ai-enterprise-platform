"""AI助手出入参（M4-T3）。"""
from pydantic import BaseModel, Field


class AIChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000, description="用户问题")
    conversation_id: int | None = Field(default=None, description="会话ID，空则新建会话")
    deep_thinking: bool = Field(default=False, description="深度思考：下发并持久化推理过程")
    images: list[str] = Field(default_factory=list, max_length=3, description="随问附带的图片 Data URL（多模态，最多3张）")


class AIConversationPatchIn(BaseModel):
    """会话编辑（M7）：title 重命名 / pinned 置顶切换，至少提供一项。"""

    title: str | None = Field(default=None, min_length=1, max_length=64, description="会话新标题（重命名）")
    pinned: bool | None = Field(default=None, description="置顶状态（置顶/取消置顶）")
