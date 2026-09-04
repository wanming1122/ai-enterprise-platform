"""sys_log 操作审计日志表模型（只读不可改删）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysLog(Base):
    __tablename__ = "sys_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), comment="操作人")
    username: Mapped[str | None] = mapped_column(String(64), comment="操作账号快照")
    module: Mapped[str | None] = mapped_column(String(64), comment="操作模块")
    action: Mapped[str | None] = mapped_column(String(64), comment="操作类型")
    method: Mapped[str | None] = mapped_column(String(16), comment="请求方法")
    path: Mapped[str | None] = mapped_column(String(255), comment="请求地址")
    params: Mapped[str | None] = mapped_column(Text, comment="请求参数")
    ip: Mapped[str | None] = mapped_column(String(64), comment="操作IP")
    device: Mapped[str | None] = mapped_column(String(128), comment="设备信息")
    result: Mapped[int] = mapped_column(TINYINT, default=1, comment="1成功 0失败")
    error_message: Mapped[str | None] = mapped_column(String(255), comment="错误信息")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, comment="接口耗时(毫秒)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
