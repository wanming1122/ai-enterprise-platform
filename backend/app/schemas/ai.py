"""AI助手出入参（M4-T3）。"""
from pydantic import BaseModel, Field


class AIChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000, description="用户问题")
    conversation_id: int | None = Field(default=None, description="会话ID，空则新建会话")
    deep_thinking: bool = Field(default=False, description="深度思考：下发并持久化推理过程")
