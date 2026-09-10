"""入职邀请服务（M5 补齐）：管理员创建邀请链接 → 外部人员通过链接注册入职。

邀请状态机：0待发送 1已发送 2已打开 3已注册 4已过期 5已撤销 6处理失败；
创建/发送/打开/注册/重发/撤销/过期 全程写入邀请日志。
"""
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import SysDepartment
from app.models.invitation import SysInvitation, SysInvitationLog
from app.models.role import SysRole
from app.models.user import SysUser
from app.models.user_role_relation import SysUserRoleRelation
from app.schemas.invitation import InvitationAcceptIn, InvitationCreateIn
from app.services.auth_service import pwd_context
from app.services.operation_log_service import write_log
from app.services.user_service import validate_password

INVITATION_STATUS = {0: "待发送", 1: "已发送", 2: "已打开", 3: "已注册", 4: "已过期", 5: "已撤销", 6: "处理失败"}
# 允许注册/重发/撤销的中间态
OPEN_STATUSES = (1, 2)


def _log(db: Session, invitation_id: int, action: str, detail: str | None = None, ip: str = "") -> None:
    db.add(SysInvitationLog(invitation_id=invitation_id, action=action, detail=detail, ip=ip))


def _expire_if_needed(db: Session, inv: SysInvitation) -> None:
    if (
        inv.expires_at is not None
        and inv.expires_at < datetime.now()
        and inv.status in (*OPEN_STATUSES, 0)
    ):
        inv.status = 4
        _log(db, inv.id, "过期", f"邀请于 {inv.expires_at:%Y-%m-%d %H:%M} 过期")
        db.commit()


def serialize_invitation(db: Session, inv: SysInvitation) -> dict:
    dept_name = db.scalar(select(SysDepartment.name).where(SysDepartment.id == inv.department_id)) if inv.department_id else None
    role_name = db.scalar(select(SysRole.name).where(SysRole.id == inv.role_id)) if inv.role_id else None
    # 仅未消费的邀请对外暴露 token/链接；已注册/撤销/过期/失败的链接已不可用，避免列表查看者直接拿去注册
    link_visible = inv.status in (0, 1, 2)
    return {
        "id": inv.id,
        "name": inv.name,
        "phone": inv.phone,
        "email": inv.email,
        "department_id": inv.department_id,
        "department_name": dept_name,
        "role_id": inv.role_id,
        "role_name": role_name,
        "post": inv.post,
        "token": inv.token if link_visible else None,
        "invite_link": inv.invite_link if link_visible else None,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "status": inv.status,
        "status_label": INVITATION_STATUS.get(inv.status, "未知"),
        "remark": inv.remark,
        "created_at": inv.created_at.isoformat(),
    }


def _validate_invitation_refs(db: Session, *, role_id: int | None, department_id: int | None) -> None:
    """校验邀请预设的部门/角色：存在、启用，且角色不得为超级管理员类型。"""
    if department_id is not None:
        dept = db.get(SysDepartment, department_id)
        if dept is None or dept.status == 2:
            raise HTTPException(status_code=422, detail="部门不存在或已删除")
    if role_id is not None:
        role = db.get(SysRole, role_id)
        if role is None or role.status != 1:
            raise HTTPException(status_code=422, detail="角色不存在或未启用")
        if role.role_type == 1:
            raise HTTPException(status_code=422, detail="邀请不可绑定超级管理员角色")


def _get_invitation(db: Session, invitation_id: int) -> SysInvitation:
    inv = db.get(SysInvitation, invitation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="邀请不存在")
    return inv


def create_invitation(db: Session, data: InvitationCreateIn, operator: SysUser) -> dict:
    _validate_invitation_refs(db, role_id=data.role_id, department_id=data.department_id)
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now() + timedelta(days=data.expires_days)
    inv = SysInvitation(
        name=data.name, phone=data.phone, email=data.email,
        department_id=data.department_id, role_id=data.role_id, post=data.post,
        token=token, invite_link=f"/invite/{token}",
        expires_at=expires_at, status=1, remark=data.remark, operator_id=operator.id,
    )
    db.add(inv)
    db.flush()
    _log(db, inv.id, "创建", f"由 {operator.username} 创建邀请")
    _log(db, inv.id, "发送", f"邀请链接 /invite/{token}，有效期至 {expires_at:%Y-%m-%d %H:%M}")
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="入职邀请",
              action="新建邀请", params={"id": inv.id, "name": data.name}, result=1)
    return serialize_invitation(db, inv)


def list_invitations(
    db: Session, *, status: int | None = None, keyword: str | None = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[dict], int]:
    q = select(SysInvitation)
    if status is not None:
        q = q.where(SysInvitation.status == status)
    if keyword:
        q = q.where(SysInvitation.name.like(f"%{keyword}%"))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(SysInvitation.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    result = []
    for inv in items:
        _expire_if_needed(db, inv)
        result.append(serialize_invitation(db, inv))
    return result, total


def resend_invitation(db: Session, invitation_id: int, operator: SysUser, days: int = 3) -> dict:
    inv = _get_invitation(db, invitation_id)
    if inv.status not in (*OPEN_STATUSES, 4):
        raise HTTPException(status_code=422, detail="仅未注册的邀请可重发")
    inv.token = secrets.token_urlsafe(24)
    inv.invite_link = f"/invite/{inv.token}"
    inv.expires_at = datetime.now() + timedelta(days=days)
    inv.status = 1
    _log(db, inv.id, "重发", f"新链接 /invite/{inv.token}，有效期至 {inv.expires_at:%Y-%m-%d %H:%M}")
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="入职邀请",
              action="重发邀请", params={"id": inv.id}, result=1)
    return serialize_invitation(db, inv)


def cancel_invitation(db: Session, invitation_id: int, operator: SysUser) -> dict:
    inv = _get_invitation(db, invitation_id)
    if inv.status not in (*OPEN_STATUSES, 0, 4):
        raise HTTPException(status_code=422, detail="该邀请当前状态不可撤销")
    inv.status = 5
    _log(db, inv.id, "撤销", f"由 {operator.username} 撤销")
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="入职邀请",
              action="撤销邀请", params={"id": inv.id}, result=1)
    return serialize_invitation(db, inv)


def delete_invitation(db: Session, invitation_id: int, operator: SysUser) -> None:
    inv = _get_invitation(db, invitation_id)
    if inv.status == 3:
        raise HTTPException(status_code=422, detail="已注册的邀请不可删除")
    # 先删日志再删邀请（无 ORM relationship，显式保证删除顺序）
    db.execute(
        sa_delete(SysInvitationLog).where(SysInvitationLog.invitation_id == inv.id)
    )
    db.flush()
    db.delete(inv)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="入职邀请",
              action="删除邀请", params={"id": invitation_id, "name": inv.name}, result=1)


def list_logs(db: Session, invitation_id: int) -> list[dict]:
    inv = _get_invitation(db, invitation_id)
    rows = db.scalars(
        select(SysInvitationLog).where(SysInvitationLog.invitation_id == inv.id).order_by(SysInvitationLog.id)
    ).all()
    return [
        {"id": x.id, "action": x.action, "detail": x.detail, "ip": x.ip,
         "created_at": x.created_at.isoformat()}
        for x in rows
    ]


def public_info(db: Session, token: str, ip: str) -> dict:
    """邀请链接打开：返回预设入职信息（公开，无鉴权）。"""
    inv = db.scalar(select(SysInvitation).where(SysInvitation.token == token))
    if inv is None:
        raise HTTPException(status_code=404, detail="邀请不存在或链接无效")
    _expire_if_needed(db, inv)
    if inv.status == 1:
        inv.status = 2
        _log(db, inv.id, "打开", f"邀请链接被打开（IP: {ip}）")
        db.commit()
    dept_name = db.scalar(select(SysDepartment.name).where(SysDepartment.id == inv.department_id)) if inv.department_id else None
    role_name = db.scalar(select(SysRole.name).where(SysRole.id == inv.role_id)) if inv.role_id else None
    return {
        "name": inv.name,
        "department_name": dept_name,
        "role_name": role_name,
        "post": inv.post,
        "status": inv.status,
        "status_label": INVITATION_STATUS.get(inv.status, "未知"),
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
    }


def accept_invitation(db: Session, token: str, data: InvitationAcceptIn, ip: str) -> dict:
    """通过邀请链接注册：创建账号并自动绑定预设部门与角色。

    行级锁（FOR UPDATE）占用邀请状态，防止同一链接并发注册出多个账号。
    """
    inv = db.scalar(select(SysInvitation).where(SysInvitation.token == token).with_for_update())
    if inv is None:
        raise HTTPException(status_code=404, detail="邀请不存在或链接无效")
    _expire_if_needed(db, inv)
    if inv.status == 3:
        raise HTTPException(status_code=422, detail="该邀请已完成注册")
    if inv.status == 5:
        raise HTTPException(status_code=422, detail="该邀请已被撤销")
    if inv.status not in OPEN_STATUSES:
        raise HTTPException(status_code=422, detail="该邀请当前不可用")
    if inv.expires_at is not None and inv.expires_at < datetime.now():
        raise HTTPException(status_code=422, detail="该邀请已过期")
    if db.scalar(select(func.count()).select_from(SysUser).where(SysUser.username == data.username)):
        raise HTTPException(status_code=422, detail="该用户名已被使用")
    validate_password(data.password)
    # 注册时二次校验预设角色（角色可能在创建后被停用/删除/改为超管类型）
    if inv.role_id:
        role = db.get(SysRole, inv.role_id)
        if role is None or role.status != 1 or role.role_type == 1:
            raise HTTPException(status_code=422, detail="邀请预设角色不可用，请联系管理员重新发送邀请")

    user = SysUser(
        username=data.username,
        password_hash=pwd_context.hash(data.password),
        nickname=inv.name,
        real_name=inv.name,
        email=inv.email,
        phone=inv.phone,
        department_id=inv.department_id,
        post=inv.post,
        status=1,
    )
    db.add(user)
    db.flush()
    if inv.role_id:
        db.add(SysUserRoleRelation(user_id=user.id, role_id=inv.role_id))
    inv.status = 3
    _log(db, inv.id, "注册", f"已注册入职，账号 {data.username}（IP: {ip}）")
    db.commit()
    write_log(db, user_id=user.id, username=data.username, module="入职邀请",
              action="邀请注册入职", params={"invitation_id": inv.id, "username": data.username}, result=1)
    return {"username": data.username, "real_name": inv.name}
