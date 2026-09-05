"""产品数据路由（M4-T2）：分页查询、新增、编辑、软删。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.product import ProductCreate, ProductUpdate
from app.services import product_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/products", tags=["产品数据"])


@router.get("")
def list_products(
    keyword: str | None = Query(default=None),
    status: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("product:list")),
    db: Session = Depends(get_db),
):
    """产品分页列表（不含软删行）。"""
    items, total = product_service.list_products(
        db, keyword=keyword, status=status, page=page, page_size=page_size
    )
    return ok(page_result(items, total, page, page_size))


@router.post("")
def create_product(
    data: ProductCreate,
    operator: SysUser = Depends(require_permissions("product:create")),
    db: Session = Depends(get_db),
):
    """新增产品。"""
    return ok(product_service.create_product(db, data, operator), message="新增成功")


@router.put("/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    operator: SysUser = Depends(require_permissions("product:update")),
    db: Session = Depends(get_db),
):
    """编辑产品。"""
    return ok(product_service.update_product(db, product_id, data, operator), message="保存成功")


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    operator: SysUser = Depends(require_permissions("product:delete")),
    db: Session = Depends(get_db),
):
    """删除产品（软删除，列表与查询均不再显示）。"""
    product_service.delete_product(db, product_id, operator)
    return ok(message="删除成功")
