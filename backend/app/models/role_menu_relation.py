"""sys_role_menu_relation 角色菜单关联表模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysRoleMenuRelation(Base):
    __tablename__ = "sys_role_menu_relation"
    __table_args__ = (UniqueConstraint("role_id", "menu_id", name="uk_role_menu"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_role.id"), nullable=False)
    menu_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_menu.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
