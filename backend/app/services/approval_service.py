"""注册审批服务（M5 补齐）：公开注册申请 → 管理员审批（通过/驳回）。

申请即创建停用账号（status=0），审批通过后账号激活并绑定申请角色，全程写审计。
"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.registration_approval import SysRegistrationApproval
from app.models.role import SysRole
from app.models.user import SysUser
from app.models.user_role_relation import SysUserRoleRelation
from app.schemas.approval import RegisterApplyIn
from app.services.auth_service import pwd_context
from app.services.operation_log_service import write_log
from app.services.user_service import validate_password

APPROVAL_STATUS = {0: "待审批", 1: "通过", 2: "驳回"}


def serialize_approval(db: Session, a: SysRegistrationApproval) -> dict:
    role_name = db.scalar(select(SysRole.name).where(SysRole.id == a.apply_role_id))
    reviewer = db.scalar(select(SysUser.username).where(SysUser.id == a.reviewer_id)) if a.reviewer_id else None
    user_status = db.scalar(select(SysUser.status).where(SysUser.id == a.user_id))
    return {
        "id": a.id,
        "user_id": a.user_id,
        "username": a.username,
        "real_name": a.real_name,
        "phone": a.phone,
        "email": a.email,
        "apply_role_id": a.apply_role_id,
        "apply_role_name": role_name,
        "status": a.status,
        "status_label": APPROVAL_STATUS.get(a.status, "未知"),
        "apply_comment": a.apply_comment,
        "review_comment": a.review_comment,
        "reviewer": reviewer,
        "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
        "account_status": user_status,
        "created_at": a.created_at.isoformat(),
    }


def _get_approval(db: Session, approval_id: int) -> SysRegistrationApproval:
    a = db.get(SysRegistrationApproval, approval_id)
    if a is None:
        raise HTTPException(status_code=404, detail="审批记录不存在")
    return a


def register_apply(db: Session, data: RegisterApplyIn, ip: str) -> dict:
    """公开注册申请：创建停用账号并生成待审批记录。"""
    exists = db.scalar(
        select(func.count()).select_from(SysUser).where(SysUser.username == data.username)
    ) or 0
    if exists:
        raise HTTPException(status_code=422, detail="该用户名已被使用")
    pending = db.scalar(
        select(func.count()).select_from(SysRegistrationApproval).where(
            SysRegistrationApproval.username == data.username,
            SysRegistrationApproval.status == 0,
        )
    ) or 0
    if pending:
        raise HTTPException(status_code=422, detail="该用户名已有待审批的注册申请")
    role = db.get(SysRole, data.apply_role_id)
    if role is None or role.status != 1 or role.role_type == 1:
        raise HTTPException(status_code=422, detail="申请角色不可用")
    validate_password(data.password)

    user = SysUser(
        username=data.username,
        password_hash=pwd_context.hash(data.password),
        nickname=data.real_name,
        real_name=data.real_name,
        email=data.email,
        phone=data.phone,
        status=0,  # 待审批激活
    )
    db.add(user)
    db.flush()
    approval = SysRegistrationApproval(
        user_id=user.id, username=data.username, real_name=data.real_name,
        phone=data.phone, email=data.email, apply_role_id=data.apply_role_id,
        status=0, apply_comment=data.apply_comment,
    )
    db.add(approval)
    db.commit()
    write_log(db, user_id=user.id, username=data.username, module="注册审批",
              action="提交注册申请", params={"username": data.username, "ip": ip}, result=1)
    return serialize_approval(db, approval)


def list_approvals(
    db: Session, *, status: int | None = None, keyword: str | None = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[dict], int]:
    q = select(SysRegistrationApproval)
    if status is not None:
        q = q.where(SysRegistrationApproval.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(SysRegistrationApproval.username.like(like) | SysRegistrationApproval.real_name.like(like))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(SysRegistrationApproval.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_approval(db, a) for a in items], total


def _finish_review(db: Session, approval_id: int, operator: SysUser, approve: bool,
                   comment: str | None, action: str) -> dict:
    a = _get_approval(db, approval_id)
    if a.status != 0:
        raise HTTPException(status_code=422, detail="仅待审批记录可审核")
    user = db.get(SysUser, a.user_id)
    if user is None:
        raise HTTPException(status_code=422, detail="申请账号不存在")
    if approve:
        user.status = 1  # 激活账号
        bound = db.scalar(
            select(SysUserRoleRelation.id).where(
                SysUserRoleRelation.user_id == user.id,
                SysUserRoleRelation.role_id == a.apply_role_id,
            )
        )
        if bound is None:
            db.add(SysUserRoleRelation(user_id=user.id, role_id=a.apply_role_id))
        a.status = 1
    else:
        a.status = 2  # 账号保持停用
    a.review_comment = comment
    a.reviewer_id = operator.id
    a.reviewed_at = datetime.now()
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="注册审批",
              action=action, params={"id": a.id, "username": a.username, "comment": comment}, result=1)
    return serialize_approval(db, a)


def approve_application(db: Session, approval_id: int, operator: SysUser) -> dict:
    return _finish_review(db, approval_id, operator, approve=True, comment=None, action="审批通过")


def reject_application(db: Session, approval_id: int, comment: str | None, operator: SysUser) -> dict:
    return _finish_review(db, approval_id, operator, approve=False, comment=comment, action="审批驳回")
