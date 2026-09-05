"""部门服务：树形查询、增删改、启停、排序，含循环父子与删除占用保护。"""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.department import SysDepartment
from app.models.user import SysUser
from app.schemas.department import DeptCreate, DeptUpdate
from app.services.operation_log_service import write_log


def _validate_parent(db: Session, parent_id: int | None, self_id: int | None = None) -> None:
    """校验上级部门存在（非软删），并禁止形成循环父子链。"""
    if parent_id is None:
        return
    parent = db.get(SysDepartment, parent_id)
    if parent is None or parent.status == 2:
        raise HTTPException(status_code=422, detail="上级部门不存在")
    if self_id is not None:
        cur = parent
        while cur is not None:
            if cur.id == self_id:
                raise HTTPException(status_code=422, detail="不能将部门移动到自身或其下级")
            cur = db.get(SysDepartment, cur.parent_id) if cur.parent_id else None


def serialize_dept(db: Session, dept: SysDepartment) -> dict:
    leader_name = None
    if dept.leader_id:
        leader = db.get(SysUser, dept.leader_id)
        leader_name = leader.real_name or leader.username if leader else None
    return {
        "id": dept.id,
        "name": dept.name,
        "parent_id": dept.parent_id,
        "leader_id": dept.leader_id,
        "leader_name": leader_name,
        "phone": dept.phone,
        "email": dept.email,
        "description": dept.description,
        "sort_order": dept.sort_order,
        "status": dept.status,
        "created_at": dept.created_at.isoformat() if dept.created_at else None,
    }


def get_tree(db: Session) -> list[dict]:
    """部门树（含停用，排除软删），按 sort_order 排序。"""
    depts = db.scalars(
        select(SysDepartment)
        .where(SysDepartment.status != 2)
        .order_by(SysDepartment.sort_order, SysDepartment.id)
    ).all()
    nodes: dict[int, dict] = {}
    for d in depts:
        item = serialize_dept(db, d)
        item["children"] = []
        nodes[d.id] = item
    roots: list[dict] = []
    for node in nodes.values():
        parent = nodes.get(node["parent_id"])
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def get_dept(db: Session, dept_id: int) -> SysDepartment:
    dept = db.get(SysDepartment, dept_id)
    if dept is None or dept.status == 2:
        raise HTTPException(status_code=404, detail="部门不存在")
    return dept


def create_dept(db: Session, data: DeptCreate, operator: SysUser) -> dict:
    _validate_parent(db, data.parent_id)
    dept = SysDepartment(
        name=data.name,
        parent_id=data.parent_id,
        leader_id=data.leader_id,
        phone=data.phone,
        email=data.email,
        description=data.description,
        sort_order=data.sort_order,
        status=data.status,
    )
    db.add(dept)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="部门管理",
              action="新增部门", params=data.model_dump(), result=1)
    return serialize_dept(db, dept)


def update_dept(db: Session, dept_id: int, data: DeptUpdate, operator: SysUser) -> dict:
    dept = get_dept(db, dept_id)
    updates = data.model_dump(exclude_unset=True)
    if "parent_id" in updates:
        _validate_parent(db, updates["parent_id"], self_id=dept_id)
    # 部分更新允许不传 name；显式传入为空才拦截
    if "name" in updates and not str(updates["name"]).strip():
        raise HTTPException(status_code=422, detail="部门名称不能为空")
    for field, value in updates.items():
        setattr(dept, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="部门管理",
              action="编辑部门", params={"id": dept_id, **updates}, result=1)
    return serialize_dept(db, dept)


def delete_dept(db: Session, dept_id: int, operator: SysUser) -> None:
    dept = get_dept(db, dept_id)
    child = db.scalar(select(SysDepartment.id).where(SysDepartment.parent_id == dept_id, SysDepartment.status != 2))
    if child is not None:
        raise HTTPException(status_code=422, detail="存在下级部门，请先处理后再删除")
    bound_user = db.scalar(
        select(SysUser.id).where(SysUser.department_id == dept_id, SysUser.status != 2)
    )
    if bound_user is not None:
        raise HTTPException(status_code=422, detail="部门下存在员工，请先处理后再删除")
    dept.status = 2  # 软删除
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="部门管理",
              action="删除部门", params={"id": dept_id}, result=1)


def toggle_status(db: Session, dept_id: int, operator: SysUser) -> dict:
    dept = get_dept(db, dept_id)
    dept.status = 0 if dept.status == 1 else 1
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="部门管理",
              action="启停部门", params={"id": dept_id, "status": dept.status}, result=1)
    return serialize_dept(db, dept)


def update_sort(db: Session, items: list[tuple[int, int]], operator: SysUser) -> None:
    """批量更新排序：items 为 [(dept_id, sort_order)]。"""
    for dept_id, sort_order in items:
        dept = db.get(SysDepartment, dept_id)
        if dept is not None:
            dept.sort_order = sort_order
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="部门管理",
              action="部门排序", params={"count": len(items)}, result=1)
