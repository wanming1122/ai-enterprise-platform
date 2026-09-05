"""sys_position 职位表模型。"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysPosition(Base):
    __tablename__ = "sys_position"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="职位名称")
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, comment="职位编码（字母开头）")
    level: Mapped[int] = mapped_column(TINYINT, default=1, comment="职级")
    base_salary: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="月基本工资"
    )
    role_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_role.id"), comment="绑定角色，决定该职位用户的权限模板"
    )
    description: Mapped[str | None] = mapped_column(String(255), comment="职位描述")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1启用 0停用 2软删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
