"""部门路由：本阶段仅提供下拉选项（完整部门管理在 M1-T4）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.department import SysDepartment
from app.models.user import SysUser
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
