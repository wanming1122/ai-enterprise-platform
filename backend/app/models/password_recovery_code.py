"""sys_password_recovery_code 密码找回表模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysPasswordRecoveryCode(Base):
    __tablename__ = "sys_password_recovery_code"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="验证码哈希")
    try_count: Mapped[int] = mapped_column(Integer, default=0, comment="已验证尝试次数")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, comment="过期时间")
    is_used: Mapped[int] = mapped_column(TINYINT, default=0, comment="0未使用 1已使用")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
