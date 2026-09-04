"""sys_invitation 入职邀请表 与 sys_invitation_log 邀请日志表模型。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SysInvitation(Base):
    __tablename__ = "sys_invitation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="被邀请人姓名")
    phone: Mapped[str | None] = mapped_column(String(20), comment="手机号")
    email: Mapped[str | None] = mapped_column(String(128), comment="邮箱")
    department_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_department.id"), comment="预设部门"
    )
    role_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_role.id"), comment="预设角色")
    post: Mapped[str | None] = mapped_column(String(64), comment="预设岗位")
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="邀请令牌")
    invite_link: Mapped[str | None] = mapped_column(String(255), comment="邀请链接")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, comment="邀请有效期")
    status: Mapped[int] = mapped_column(
        TINYINT, default=0, comment="0待发送 1已发送 2已打开 3已注册 4已过期 5已撤销 6处理失败"
    )
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), comment="创建人")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class SysInvitationLog(Base):
    __tablename__ = "sys_invitation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invitation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_invitation.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False, comment="状态动作：创建/发送/打开/注册/重发/撤销/过期/失败")
    detail: Mapped[str | None] = mapped_column(String(255), comment="详情")
    ip: Mapped[str | None] = mapped_column(String(64), comment="操作IP")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
