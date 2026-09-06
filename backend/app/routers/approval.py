"""注册审批路由（M5 补齐）：分页列表、通过、驳回。公开申请入口在 auth 路由。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.approval import ApprovalRejectIn
from app.services import approval_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/approvals", tags=["注册审批"])


@router.get("")
def list_approvals(
    status: int | None = Query(default=None, ge=0, le=2),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("approval:list")),
    db: Session = Depends(get_db),
):
    """注册申请分页列表。"""
    items, total = approval_service.list_approvals(
        db, status=status, keyword=keyword, page=page, page_size=page_size
    )
    return ok(page_result(items, total, page, page_size))


@router.post("/{approval_id}/approve")
def approve(
    approval_id: int,
    operator: SysUser = Depends(require_permissions("approval:approve")),
    db: Session = Depends(get_db),
):
    """审批通过：激活账号并绑定申请角色。"""
    return ok(approval_service.approve_application(db, approval_id, operator), message="已通过")


@router.post("/{approval_id}/reject")
def reject(
    approval_id: int,
    data: ApprovalRejectIn,
    operator: SysUser = Depends(require_permissions("approval:reject")),
    db: Session = Depends(get_db),
):
    """审批驳回：账号保持停用。"""
    return ok(
        approval_service.reject_application(db, approval_id, data.comment, operator),
        message="已驳回",
    )
