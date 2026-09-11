"""工作台看板路由（M5-T1）：只读统计聚合。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.services import dashboard_service
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/dashboard", tags=["工作台"])


@router.get("/summary")
def get_summary(
    user: SysUser = Depends(require_permissions("dashboard:view")),
    db: Session = Depends(get_db),
):
    """工作台统计汇总：卡片数据 + 图表分布（管理员全量，普通员工仅基础看板）。"""
    return ok(dashboard_service.get_summary(db, user))
