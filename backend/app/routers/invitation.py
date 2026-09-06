"""入职邀请路由（M5 补齐）：管理端增删改查 + 公开链接打开与注册。"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.invitation import InvitationAcceptIn, InvitationCreateIn
from app.services import invitation_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/invitations", tags=["入职邀请"])


@router.get("")
def list_invitations(
    status: int | None = Query(default=None, ge=0, le=6),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("invitation:list")),
    db: Session = Depends(get_db),
):
    """邀请分页列表。"""
    items, total = invitation_service.list_invitations(
        db, status=status, keyword=keyword, page=page, page_size=page_size
    )
    return ok(page_result(items, total, page, page_size))


@router.post("")
def create_invitation(
    data: InvitationCreateIn,
    operator: SysUser = Depends(require_permissions("invitation:create")),
    db: Session = Depends(get_db),
):
    """新建入职邀请并生成邀请链接。"""
    return ok(invitation_service.create_invitation(db, data, operator), message="邀请已创建")


@router.post("/{invitation_id}/resend")
def resend_invitation(
    invitation_id: int,
    operator: SysUser = Depends(require_permissions("invitation:resend")),
    db: Session = Depends(get_db),
):
    """重发邀请：重新生成链接并顺延有效期。"""
    return ok(invitation_service.resend_invitation(db, invitation_id, operator), message="已重发")


@router.post("/{invitation_id}/cancel")
def cancel_invitation(
    invitation_id: int,
    operator: SysUser = Depends(require_permissions("invitation:revoke")),
    db: Session = Depends(get_db),
):
    """撤销邀请。"""
    return ok(invitation_service.cancel_invitation(db, invitation_id, operator), message="已撤销")


@router.delete("/{invitation_id}")
def delete_invitation(
    invitation_id: int,
    operator: SysUser = Depends(require_permissions("invitation:delete")),
    db: Session = Depends(get_db),
):
    """删除邀请（已注册的不可删）。"""
    invitation_service.delete_invitation(db, invitation_id, operator)
    return ok(message="删除成功")


@router.get("/{invitation_id}/logs")
def list_logs(
    invitation_id: int,
    _: SysUser = Depends(require_permissions("invitation:list")),
    db: Session = Depends(get_db),
):
    """邀请状态日志。"""
    return ok(invitation_service.list_logs(db, invitation_id))


@router.get("/public/{token}")
def public_info(token: str, request: Request, db: Session = Depends(get_db)):
    """邀请链接打开（公开）：返回预设入职信息。"""
    ip = request.client.host if request.client else ""
    return ok(invitation_service.public_info(db, token, ip))


@router.post("/public/{token}/accept")
def accept_invitation(
    token: str,
    data: InvitationAcceptIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """通过邀请链接注册入职（公开）：创建账号并绑定预设部门与角色。"""
    ip = request.client.host if request.client else ""
    return ok(invitation_service.accept_invitation(db, token, data, ip), message="注册成功，欢迎入职！")
