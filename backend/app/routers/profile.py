"""个人中心路由：资料修改 / 修改密码 / 我的考勤 / 我的薪资（仅登录用户，强制本人数据）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.profile import PasswordChange, PreferencesUpdate, ProfileUpdate
from app.services import profile_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/profile", tags=["个人中心"])


@router.put("")
def update_profile(
    data: ProfileUpdate,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改本人资料。"""
    return ok(profile_service.update_profile(db, user, data), message="保存成功")


@router.put("/preferences")
def update_preferences(
    data: PreferencesUpdate,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改个人偏好设置（默认首页/侧边栏折叠/消息提醒，合并式更新）。"""
    return ok(profile_service.update_preferences(db, user, data), message="偏好已保存")


@router.put("/password")
def change_password(
    data: PasswordChange,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改密码：校验旧密码与新密码强度。"""
    profile_service.change_password(db, user, data)
    return ok(message="密码修改成功，请重新登录")


@router.get("/attendance")
def my_attendance(
    month: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    user: SysUser = Depends(require_permissions("attendance:view")),
    db: Session = Depends(get_db),
):
    """我的考勤分页列表（仅本人数据）。"""
    items, total = profile_service.my_attendance(db, user, month=month, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.get("/salary")
def my_salaries(
    year_month: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    user: SysUser = Depends(require_permissions("salary:view")),
    db: Session = Depends(get_db),
):
    """我的工资单分页列表（仅本人数据）。"""
    items, total = profile_service.my_salaries(db, user, year_month=year_month, page=page, page_size=page_size)
    return ok(page_result(items, total, page, page_size))


@router.get("/salary/{payroll_id}")
def my_salary_detail(
    payroll_id: int,
    user: SysUser = Depends(require_permissions("salary:view")),
    db: Session = Depends(get_db),
):
    """我的工资单明细（非本人返回 404）。"""
    return ok(profile_service.my_salary_detail(db, user, payroll_id))
