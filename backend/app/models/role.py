"""sys_role 角色表模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysRole(Base):
    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="角色名称")
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, comment="角色编码（字母开头）")
    role_type: Mapped[int] = mapped_column(TINYINT, default=3, comment="1超级管理员 2普通管理员 3普通员工")
    data_scope: Mapped[int] = mapped_column(TINYINT, default=3, comment="数据范围: 1仅本人 2本部门 3全部")
    description: Mapped[str | None] = mapped_column(String(255), comment="角色描述")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1启用 0停用 2软删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
