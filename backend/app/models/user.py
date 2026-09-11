"""sys_user 用户表模型。"""
from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysUser(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="登录账号")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="bcrypt哈希密码")
    nickname: Mapped[str | None] = mapped_column(String(64), comment="昵称")
    real_name: Mapped[str | None] = mapped_column(String(64), comment="真实姓名")
    gender: Mapped[int] = mapped_column(TINYINT, default=0, comment="0未知 1男 2女")
    birthday: Mapped[date | None] = mapped_column(Date, comment="生日")
    email: Mapped[str | None] = mapped_column(String(128), comment="邮箱")
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, comment="手机号")
    social_account: Mapped[str | None] = mapped_column(String(128), comment="社交账号")
    department_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_department.id"), comment="所属部门"
    )
    position_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_position.id"), comment="职位（M2 起替代岗位文本）"
    )
    post: Mapped[str | None] = mapped_column(String(64), comment="岗位（M1 遗留文本字段，保留兼容）")
    avatar: Mapped[str | None] = mapped_column(Text, comment="头像（Data URL）")
    status: Mapped[int] = mapped_column(TINYINT, default=1, comment="1正常 0停用 2软删除")
    need_reset_pwd: Mapped[int] = mapped_column(TINYINT, default=0, comment="0否 1是（管理员重置密码后标记）")
    preferences: Mapped[dict | None] = mapped_column(JSON, comment="个性化配置：主题/布局/消息提醒/默认首页")
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, comment="连续登录失败次数")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, comment="账号锁定截止时间")
    last_login_ip: Mapped[str | None] = mapped_column(String(64), comment="最近登录IP")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最近登录时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
