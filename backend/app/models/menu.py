"""sys_menu 菜单表模型（目录/页面/按钮 三类）。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysMenu(Base):
    __tablename__ = "sys_menu"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_menu.id"), comment="父菜单ID"
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="菜单名称")
    type: Mapped[int] = mapped_column(TINYINT, default=2, comment="1目录 2页面 3按钮")
    path: Mapped[str | None] = mapped_column(String(255), comment="前端路由路径")
    component: Mapped[str | None] = mapped_column(String(255), comment="组件映射地址")
    icon: Mapped[str | None] = mapped_column(String(64), comment="图标样式")
    permission_code: Mapped[str | None] = mapped_column(String(64), comment="权限标识（按钮必填）")
    visible: Mapped[int] = mapped_column(TINYINT, default=1, comment="1显示 0隐藏")
    is_external: Mapped[int] = mapped_column(TINYINT, default=0, comment="0站内 1外链")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序序号")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1启用 0停用 2软删除")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
