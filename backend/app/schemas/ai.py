"""AI助手出入参（M4-T3）。"""
from pydantic import BaseModel, Field, field_validator


class AIChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000, description="用户问题")
    conversation_id: int | None = Field(default=None, description="会话ID，空则新建会话")
    deep_thinking: bool = Field(default=False, description="深度思考：下发并持久化推理过程")
    images: list[str] = Field(default_factory=list, max_length=3, description="随问附带的图片 Data URL（多模态，最多3张）")
    model_id: int | None = Field(default=None, description="指定生成模型配置ID；空则用默认模型。无效/停用时后端回退默认")
    kb_ids: list[int] | None = Field(default=None, max_length=20, description="限定知识库检索范围（kb问答调试用；空则全库）")
    source: str = Field(default="ai", description="会话来源：ai AI助手 / kb 问答调试")

    @field_validator("source")
    @classmethod
    def _check_source(cls, v: str) -> str:
        if v not in ("ai", "kb"):
            raise ValueError("source 仅支持 ai/kb")
        return v


class AIConversationPatchIn(BaseModel):
    """会话编辑（M7）：title 重命名 / pinned 置顶切换，至少提供一项。"""

    title: str | None = Field(default=None, min_length=1, max_length=64, description="会话新标题（重命名）")
    pinned: bool | None = Field(default=None, description="置顶状态（置顶/取消置顶）")
