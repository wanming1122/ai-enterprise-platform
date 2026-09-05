"""部门路由：树形查询、增删改、启停、排序与下拉选项。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.department import SysDepartment
from app.models.user import SysUser
from app.schemas.department import DeptCreate, DeptSortItem, DeptUpdate
from app.services import department_service
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/departments", tags=["部门管理"])


@router.get("/options")
def department_options(
    _: SysUser = Depends(require_permissions("user:list")),
    db: Session = Depends(get_db),
):
    """启用部门树（供用户管理等下拉选择）。"""
    depts = db.scalars(select(SysDepartment).where(SysDepartment.status == 1).order_by(SysDepartment.sort_order)).all()
    nodes: dict[int, dict] = {
        d.id: {"id": d.id, "name": d.name, "parent_id": d.parent_id, "children": []}
        for d in depts
    }
    roots: list[dict] = []
    for node in nodes.values():
        parent = nodes.get(node["parent_id"])
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)
    return ok(roots)


@router.get("/tree")
def dept_tree(
    _: SysUser = Depends(require_permissions("dept:list")),
    db: Session = Depends(get_db),
):
    """部门树（含停用，排除软删）。"""
    return ok(department_service.get_tree(db))


@router.post("")
def create_dept(
    data: DeptCreate,
    operator: SysUser = Depends(require_permissions("dept:create")),
    db: Session = Depends(get_db),
):
    """新增部门（支持新增下级部门）。"""
    return ok(department_service.create_dept(db, data, operator), message="新增成功")


@router.post("/sort")
def sort_depts(
    items: list[DeptSortItem],
    operator: SysUser = Depends(require_permissions("dept:sort")),
    db: Session = Depends(get_db),
):
    """批量调整部门排序。"""
    department_service.update_sort(db, [(i.id, i.sort_order) for i in items], operator)
    return ok(message="排序已保存")


@router.put("/{dept_id}")
def update_dept(
    dept_id: int,
    data: DeptUpdate,
    operator: SysUser = Depends(require_permissions("dept:update")),
    db: Session = Depends(get_db),
):
    """编辑部门（含上级部门调整，禁止循环父子）。"""
    return ok(department_service.update_dept(db, dept_id, data, operator), message="编辑成功")


@router.delete("/{dept_id}")
def delete_dept(
    dept_id: int,
    operator: SysUser = Depends(require_permissions("dept:delete")),
    db: Session = Depends(get_db),
):
    """软删部门（有子部门或绑定员工时禁止）。"""
    department_service.delete_dept(db, dept_id, operator)
    return ok(message="删除成功")


@router.put("/{dept_id}/status")
def toggle_status(
    dept_id: int,
    operator: SysUser = Depends(require_permissions("dept:toggle")),
    db: Session = Depends(get_db),
):
    """启停部门。"""
    return ok(department_service.toggle_status(db, dept_id, operator), message="操作成功")
