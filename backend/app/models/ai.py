"""AI 智能中心模型：ai_model 模型配置、ai_conversation 会话、ai_message 消息。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIModel(Base):
    """模型配置表（M4-T1）：生成/向量/重排三类，api_key Fernet 加密存储。"""

    __tablename__ = "ai_model"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="配置名称")
    model_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="llm/embedding/rerank")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, comment="zhipu/dashscope/openai_compatible/local")
    base_url: Mapped[str | None] = mapped_column(String(255), comment="API地址，缺省用提供方默认端点")
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, comment="Fernet 加密后的密钥")
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="模型标识，如 mimo-v2.5")
    temperature: Mapped[float | None] = mapped_column(Numeric(3, 2), comment="生成温度（仅 llm）")
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")
    is_default: Mapped[bool] = mapped_column(SmallInteger, default=0, nullable=False, comment="同类型仅一个默认")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False, comment="1启用 0停用 2软删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class AIConversation(Base):
    __tablename__ = "ai_conversation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False, comment="归属用户")
    title: Mapped[str | None] = mapped_column(String(64), comment="会话标题（取首问，可重命名）")
    pinned: Mapped[int] = mapped_column(TINYINT, default=0, nullable=False, comment="1置顶 0普通（列表置顶优先）")
    status: Mapped[int] = mapped_column(TINYINT, default=1, nullable=False, comment="1正常 2软删除")
    source: Mapped[str] = mapped_column(String(16), default="kb", nullable=False, comment="会话来源：kb问答调试 / ai AI助手")
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
    reasoning_content: Mapped[str | None] = mapped_column(Text, comment="深度思考过程（推理模型）")
    tool_name: Mapped[str | None] = mapped_column(String(32), comment="工具名（AI助手用）")
    citations: Mapped[list | None] = mapped_column(JSON, comment="引用来源列表")
    attachments: Mapped[list | None] = mapped_column(JSON, comment="附件列表（多模态图片 Data URL）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
