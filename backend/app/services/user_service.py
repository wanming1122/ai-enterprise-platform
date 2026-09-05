"""用户服务：CRUD、启停、重置密码、角色绑定、Excel 导入导出与模板。"""
import re
import secrets
from datetime import datetime

from fastapi import HTTPException, UploadFile
from passlib.context import CryptContext
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.department import SysDepartment
from app.models.position import SysPosition
from app.models.role import SysRole
from app.models.user import SysUser
from app.models.user_role_relation import SysUserRoleRelation
from app.schemas.user import UserCreate, UserUpdate
from app.services.operation_log_service import write_log
from app.services.position_service import sync_position_role
from app.utils.excel import export_workbook, read_workbook

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

IMPORT_HEADERS = ["账号", "姓名", "昵称", "手机", "邮箱", "部门", "职位", "角色", "初始密码"]
EXPORT_HEADERS = ["账号", "姓名", "昵称", "手机", "邮箱", "部门", "职位", "角色", "状态", "最近登录时间"]
DEFAULT_IMPORT_PASSWORD = "admin123456"


def validate_password(password: str) -> None:
    """强密码规则：至少 8 位且同时包含字母与数字。"""
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(status_code=422, detail="密码需至少8位且包含字母和数字")


def _set_user_roles(db: Session, user_id: int, role_ids: list[int]) -> None:
    """重建用户角色绑定（先删后插）。"""
    if role_ids:
        exists = set(db.scalars(select(SysRole.id).where(SysRole.id.in_(role_ids), SysRole.status != 2)).all())
        invalid = set(role_ids) - exists
        if invalid:
            raise HTTPException(status_code=422, detail="存在无效的角色ID")
    db.execute(
        SysUserRoleRelation.__table__.delete().where(SysUserRoleRelation.user_id == user_id)
    )
    for rid in role_ids:
        db.add(SysUserRoleRelation(user_id=user_id, role_id=rid))
    db.flush()


def serialize_user(db: Session, user: SysUser) -> dict:
    """序列化用户（含部门名、职位与角色编码）。"""
    dept_name = None
    if user.department_id:
        dept = db.get(SysDepartment, user.department_id)
        dept_name = dept.name if dept else None
    position_name = None
    if user.position_id:
        position = db.get(SysPosition, user.position_id)
        position_name = position.name if position and position.status != 2 else None
    role_codes = db.scalars(
        select(SysRole.code)
        .join(SysUserRoleRelation, SysUserRoleRelation.role_id == SysRole.id)
        .where(SysUserRoleRelation.user_id == user.id, SysRole.status != 2)
    ).all()
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "real_name": user.real_name,
        "gender": user.gender,
        "birthday": user.birthday.isoformat() if user.birthday else None,
        "email": user.email,
        "phone": user.phone,
        "department_id": user.department_id,
        "dept_name": dept_name,
        "position_id": user.position_id,
        "position_name": position_name,
        "post": user.post,
        "roles": role_codes,
        "status": user.status,
        "need_reset_pwd": user.need_reset_pwd,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _build_filter(
    db: Session,
    *,
    keyword: str | None,
    department_id: int | None,
    role_id: int | None,
    status: int | None,
):
    q = select(SysUser).where(SysUser.status != 2)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            or_(SysUser.username.like(like), SysUser.real_name.like(like), SysUser.phone.like(like))
        )
    if department_id:
        q = q.where(SysUser.department_id == department_id)
    if role_id:
        q = q.join(SysUserRoleRelation, SysUserRoleRelation.user_id == SysUser.id).where(
            SysUserRoleRelation.role_id == role_id
        )
    if status is not None:
        q = q.where(SysUser.status == status)
    return q


def list_users(
    db: Session,
    *,
    keyword: str | None = None,
    department_id: int | None = None,
    role_id: int | None = None,
    status: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    q = _build_filter(db, keyword=keyword, department_id=department_id, role_id=role_id, status=status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    users = db.scalars(
        q.order_by(SysUser.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_user(db, u) for u in users], total


def get_user(db: Session, user_id: int) -> SysUser:
    user = db.get(SysUser, user_id)
    if user is None or user.status == 2:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def _validate_position(db: Session, position_id: int | None) -> None:
    if position_id is not None:
        position = db.get(SysPosition, position_id)
        if position is None or position.status != 1:
            raise HTTPException(status_code=422, detail="职位不存在或已停用")


def create_user(db: Session, data: UserCreate, operator: SysUser) -> dict:
    if db.scalar(select(SysUser).where(SysUser.username == data.username)):
        raise HTTPException(status_code=422, detail="账号已存在")
    validate_password(data.password)
    _validate_position(db, data.position_id)
    user = SysUser(
        username=data.username,
        password_hash=pwd_context.hash(data.password),
        nickname=data.nickname,
        real_name=data.real_name,
        gender=data.gender,
        birthday=data.birthday,
        email=data.email,
        phone=data.phone,
        department_id=data.department_id,
        position_id=data.position_id,
        post=data.post,
        status=1,
    )
    db.add(user)
    db.flush()
    _set_user_roles(db, user.id, data.role_ids)
    # 职位绑定角色时，新用户选该职位自动并入对应权限模板角色
    sync_position_role(db, user.id, None, data.position_id)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="用户管理",
              action="新增用户", params=data.model_dump(exclude={"password"}), result=1)
    return serialize_user(db, user)


def update_user(db: Session, user_id: int, data: UserUpdate, operator: SysUser) -> dict:
    user = get_user(db, user_id)
    updates = data.model_dump(exclude_unset=True)
    role_ids = updates.pop("role_ids", None)
    old_position_id = user.position_id
    if "position_id" in updates:
        _validate_position(db, updates["position_id"])
    for field, value in updates.items():
        setattr(user, field, value)
    if role_ids is not None:
        _set_user_roles(db, user.id, role_ids)
    # 职位变更时同步权限模板角色：移除旧职位角色、并入新职位角色
    sync_position_role(db, user.id, old_position_id, user.position_id)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="用户管理",
              action="编辑用户", params={"id": user_id, **data.model_dump(exclude_unset=True)}, result=1)
    return serialize_user(db, user)


def delete_user(db: Session, user_id: int, operator: SysUser) -> None:
    if user_id == operator.id:
        raise HTTPException(status_code=422, detail="不能删除当前登录账号")
    user = get_user(db, user_id)
    user.status = 2  # 软删除
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="用户管理",
              action="删除用户", params={"id": user_id}, result=1)


def toggle_status(db: Session, user_id: int, operator: SysUser) -> dict:
    if user_id == operator.id:
        raise HTTPException(status_code=422, detail="不能停用当前登录账号")
    user = get_user(db, user_id)
    user.status = 0 if user.status == 1 else 1
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="用户管理",
              action="启停用户", params={"id": user_id, "status": user.status}, result=1)
    return serialize_user(db, user)


def reset_password(db: Session, user_id: int, operator: SysUser) -> str:
    user = get_user(db, user_id)
    temp_password = secrets.token_urlsafe(8).replace("-", "_")
    user.password_hash = pwd_context.hash(temp_password)
    user.need_reset_pwd = 1  # 首次登录需修改密码
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="用户管理",
              action="重置密码", params={"id": user_id}, result=1)
    return temp_password


def import_users(db: Session, file: UploadFile, operator: SysUser) -> dict:
    """Excel 批量导入：逐行校验，错误行跳过并报告。"""
    content = file.file.read()
    rows = read_workbook(content, IMPORT_HEADERS)

    dept_map = {d.name: d.id for d in db.scalars(select(SysDepartment).where(SysDepartment.status != 2)).all()}
    role_map = {r.code: r.id for r in db.scalars(select(SysRole).where(SysRole.status != 2)).all()}
    position_map = {p.name: p.id for p in db.scalars(select(SysPosition).where(SysPosition.status == 1)).all()}
    existing = set(db.scalars(select(SysUser.username)).all())

    success = 0
    errors: list[dict] = []
    for idx, row in enumerate(rows, start=2):  # 行号从表头下一行起
        username = row.get("账号", "")
        if not username:
            errors.append({"row": idx, "reason": "账号为空"})
            continue
        if username in existing:
            errors.append({"row": idx, "reason": f"账号 {username} 已存在"})
            continue
        password = row.get("初始密码") or DEFAULT_IMPORT_PASSWORD
        try:
            validate_password(password)
        except HTTPException:
            errors.append({"row": idx, "reason": "初始密码需至少8位且含字母和数字"})
            continue
        dept_name = row.get("部门", "")
        department_id = dept_map.get(dept_name) if dept_name else None
        if dept_name and department_id is None:
            errors.append({"row": idx, "reason": f"部门 {dept_name} 不存在"})
            continue
        position_name = row.get("职位", "")
        position_id = position_map.get(position_name) if position_name else None
        if position_name and position_id is None:
            errors.append({"row": idx, "reason": f"职位 {position_name} 不存在或已停用"})
            continue
        role_codes = [c.strip() for c in row.get("角色", "").split(",") if c.strip()]
        role_ids: list[int] = []
        invalid_role = None
        for code in role_codes:
            rid = role_map.get(code)
            if rid is None:
                invalid_role = code
                break
            role_ids.append(rid)
        if invalid_role:
            errors.append({"row": idx, "reason": f"角色 {invalid_role} 不存在"})
            continue

        user = SysUser(
            username=username,
            password_hash=pwd_context.hash(password),
            nickname=row.get("昵称") or None,
            real_name=row.get("姓名") or None,
            phone=row.get("手机") or None,
            email=row.get("邮箱") or None,
            department_id=department_id,
            position_id=position_id,
            status=1,
        )
        db.add(user)
        db.flush()
        _set_user_roles(db, user.id, role_ids)
        sync_position_role(db, user.id, None, position_id)
        existing.add(username)
        success += 1

    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="用户管理",
              action="导入用户", params={"total": len(rows), "success": success, "failed": len(errors)}, result=1)
    return {"total": len(rows), "success": success, "failed": len(errors), "errors": errors}


def export_users(
    db: Session,
    *,
    keyword: str | None = None,
    department_id: int | None = None,
    role_id: int | None = None,
    status: int | None = None,
) -> bytes:
    """按当前筛选条件导出全部用户（不分页）。"""
    q = _build_filter(db, keyword=keyword, department_id=department_id, role_id=role_id, status=status)
    users = db.scalars(q.order_by(SysUser.id.desc())).all()

    status_text = {1: "正常", 0: "停用"}
    dept_names = {d.id: d.name for d in db.scalars(select(SysDepartment)).all()}
    position_names = {p.id: p.name for p in db.scalars(select(SysPosition)).all()}
    rows = []
    for u in users:
        role_codes = db.scalars(
            select(SysRole.code)
            .join(SysUserRoleRelation, SysUserRoleRelation.role_id == SysRole.id)
            .where(SysUserRoleRelation.user_id == u.id)
        ).all()
        rows.append([
            u.username,
            u.real_name or "",
            u.nickname or "",
            u.phone or "",
            u.email or "",
            dept_names.get(u.department_id, "") if u.department_id else "",
            position_names.get(u.position_id, "") if u.position_id else "",
            "/".join(role_codes),
            status_text.get(u.status, ""),
            u.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if u.last_login_at else "",
        ])
    return export_workbook(EXPORT_HEADERS, rows)


def get_template() -> bytes:
    """导入模板：表头 + 示例行。"""
    sample = [
        "zhangsan", "张三", "三哥", "13800000001", "zhangsan@example.com",
        "技术部", "软件工程师", "employee", "admin123456",
    ]
    return export_workbook(IMPORT_HEADERS, [sample])
