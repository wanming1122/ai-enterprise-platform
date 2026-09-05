"""AI 智能中心会话模型：ai_conversation 会话表、ai_message 消息表（RAG 与 AI助手共用）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIConversation(Base):
    __tablename__ = "ai_conversation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="归属用户")
    title: Mapped[str | None] = mapped_column(String(64), comment="会话标题（取首问）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class AIMessage(Base):
    __tablename__ = "ai_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_conversation.id"), nullable=False, comment="所属会话"
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, comment="user/assistant/tool")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    tool_name: Mapped[str | None] = mapped_column(String(32), comment="工具名（AI助手用）")
    citations: Mapped[list | None] = mapped_column(JSON, comment="引用来源列表")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
