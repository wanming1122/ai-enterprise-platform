"""sys_config 系统配置表模型（图片以 Data URL 存储）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysConfig(Base):
    __tablename__ = "sys_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="配置键")
    config_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="配置名称")
    config_value: Mapped[str | None] = mapped_column(Text, comment="配置值（Data URL 图片等）")
    description: Mapped[str | None] = mapped_column(String(255), comment="配置说明")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
