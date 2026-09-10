"""个人中心服务：本人资料修改、修改密码、我的考勤与我的薪资（强制本人数据）。"""
from datetime import date, datetime

from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.user import SysUser
from app.schemas.profile import PasswordChange, PreferencesUpdate, ProfileUpdate
from app.services import salary_service
from app.services.attendance_service import list_records as list_attendance_records
from app.services.operation_log_service import write_log
from app.services.user_service import validate_password

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Data URL 头像上限（约 300KB 压缩后体积）
MAX_AVATAR_LEN = 400_000

# 偏好设置默认值：未设置时前端按此回退
DEFAULT_PREFERENCES = {
    "default_home": "/dashboard", "sidebar_collapsed": False,
    "notify_enabled": True, "theme": "light", "ai_memory_enabled": True,
    "default_model": None,  # AI 助手默认生成模型ID；空则后端用启用中的默认模型
}


def _parse_birthday(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="生日格式应为 YYYY-MM-DD") from exc


def _validate_avatar(avatar: str | None) -> None:
    if avatar and (not avatar.startswith("data:image/") or len(avatar) > MAX_AVATAR_LEN):
        raise HTTPException(status_code=422, detail="头像需为压缩后的图片 Data URL 且不超过 400KB")


def update_profile(db: Session, user: SysUser, data: ProfileUpdate) -> dict:
    """修改本人资料（仅个人字段，不含账号/部门/职位/角色）。"""
    updates = data.model_dump(exclude_unset=True)
    if "birthday" in updates:
        updates["birthday"] = _parse_birthday(updates["birthday"])
    if "gender" in updates and updates["gender"] not in (0, 1, 2):
        raise HTTPException(status_code=422, detail="性别取值应为 0未知/1男/2女")
    _validate_avatar(updates.get("avatar"))
    for field, value in updates.items():
        setattr(user, field, value)
    db.commit()
    write_log(db, user_id=user.id, username=user.username, module="个人中心",
              action="修改个人资料", params=data.model_dump(exclude_unset=True, exclude={"avatar"}), result=1)
    return {"updated": len(updates)}


def update_preferences(db: Session, user: SysUser, data: PreferencesUpdate) -> dict:
    """合并式更新个人偏好（白名单键；default_home 必须是站内路径）。

    显式传 null 表示清除该项（恢复系统默认），而非被静默忽略。
    """
    raw_updates = data.model_dump(exclude_unset=True)
    updates = {k: v for k, v in raw_updates.items() if v is not None}
    resets = [k for k, v in raw_updates.items() if v is None]
    if "default_home" in updates:
        path = updates["default_home"]
        if not (isinstance(path, str) and path.startswith("/") and len(path) <= 128):
            raise HTTPException(status_code=422, detail="默认首页需为站内路径（以 / 开头）")
    if "theme" in updates and updates["theme"] not in ("light", "dark"):
        raise HTTPException(status_code=422, detail="主题仅支持 light/dark")
    prefs: dict = dict(user.preferences or {})
    for k in resets:
        prefs.pop(k, None)
    prefs.update(updates)
    user.preferences = prefs
    db.commit()
    write_log(db, user_id=user.id, username=user.username, module="个人中心",
              action="修改偏好设置", params=updates, result=1)
    return prefs


def change_password(db: Session, user: SysUser, data: PasswordChange) -> None:
    """修改密码：校验旧密码与新密码强度，清除强制改密标记。"""
    if not pwd_context.verify(data.old_password, user.password_hash):
        write_log(db, user_id=user.id, username=user.username, module="个人中心",
                  action="修改密码", result=0, error_message="旧密码错误")
        raise HTTPException(status_code=422, detail="旧密码错误")
    validate_password(data.new_password)
    user.password_hash = pwd_context.hash(data.new_password)
    user.need_reset_pwd = 0
    db.commit()
    write_log(db, user_id=user.id, username=user.username, module="个人中心",
              action="修改密码", result=1)


def my_attendance(
    db: Session, user: SysUser, *, month: str | None = None, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    """我的考勤：强制 user_id 为当前登录人。"""
    return list_attendance_records(
        db, user_id=user.id, month=month, page=page, page_size=page_size
    )


def my_salaries(
    db: Session, user: SysUser, *, year_month: str | None = None, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    """我的工资单：强制 user_id 为当前登录人。"""
    return salary_service.list_payrolls(
        db, year_month=year_month, user_id=user.id, page=page, page_size=page_size
    )


def my_salary_detail(db: Session, user: SysUser, payroll_id: int) -> dict:
    """我的工资单明细：非本人工资单一律 404，不泄露存在性。"""
    detail = salary_service.payroll_detail(db, payroll_id)
    if detail["payroll"]["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="工资单不存在")
    return detail
