"""产品数据服务（M4-T2）：分页查询、CRUD、软删。"""
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.nl2sql import Product
from app.models.user import SysUser
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.operation_log_service import write_log

PRODUCT_STATUS = {1: "上架", 0: "下架"}


def serialize_product(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "price": float(p.price) if p.price is not None else None,
        "stock": p.stock,
        "description": p.description,
        "status": p.status,
        "status_label": PRODUCT_STATUS.get(p.status, "未知"),
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


def get_product(db: Session, product_id: int) -> Product:
    p = db.get(Product, product_id)
    if p is None or p.status == 2:
        raise HTTPException(status_code=404, detail="产品不存在")
    return p


def list_products(
    db: Session, *, keyword: str | None = None, status: int | None = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[dict], int]:
    q = select(Product).where(Product.status != 2)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(Product.name.like(like), Product.category.like(like), Product.description.like(like)))
    if status is not None:
        q = q.where(Product.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(
        q.order_by(Product.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [serialize_product(p) for p in items], total


def create_product(db: Session, data: ProductCreate, operator: SysUser) -> dict:
    p = Product(**data.model_dump())
    db.add(p)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="产品数据",
              action="新增产品", params=data.model_dump(), result=1)
    return serialize_product(p)


def update_product(db: Session, product_id: int, data: ProductUpdate, operator: SysUser) -> dict:
    p = get_product(db, product_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="产品数据",
              action="编辑产品", params={"id": product_id, **data.model_dump(exclude_unset=True)}, result=1)
    return serialize_product(p)


def delete_product(db: Session, product_id: int, operator: SysUser) -> None:
    p = get_product(db, product_id)
    p.status = 2  # 软删除
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="产品数据",
              action="删除产品", params={"id": product_id}, result=1)
