"""操作审计日志路由（M5-T2 补齐）：分页查询，只读。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.log import SysLog
from app.models.user import SysUser
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/logs", tags=["操作日志"])


def _serialize_log(log: SysLog) -> dict:
    return {
        "id": log.id,
        "username": log.username,
        "module": log.module,
        "action": log.action,
        "method": log.method,
        "path": log.path,
        "params": log.params,
        "ip": log.ip,
        "result": log.result,
        "error_message": log.error_message,
        "duration_ms": log.duration_ms,
        "created_at": log.created_at.isoformat(),
    }


@router.get("")
def list_logs(
    keyword: str | None = Query(default=None, description="账号/操作/路径模糊搜索"),
    module: str | None = Query(default=None),
    result: int | None = Query(default=None, ge=0, le=1),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("log:list")),
    db: Session = Depends(get_db),
):
    """操作审计日志分页列表（只读，不做增删改）。"""
    q = select(SysLog)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(SysLog.username.like(like) | SysLog.action.like(like) | SysLog.path.like(like))
    if module:
        q = q.where(SysLog.module == module)
    if result is not None:
        q = q.where(SysLog.result == result)
    if start_date:
        q = q.where(SysLog.created_at >= start_date)
    if end_date:
        q = q.where(SysLog.created_at < date.fromordinal(end_date.toordinal() + 1))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(SysLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ok(page_result([_serialize_log(x) for x in items], total, page, page_size))
