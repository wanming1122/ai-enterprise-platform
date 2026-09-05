"""模型配置路由（M4-T1）：CRUD、设默认、连通性测试。api_key 仅返回掩码。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.ai_model import AIModelCreate, AIModelUpdate
from app.services import ai_model_service
from app.utils.page import page_result
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/ai/models", tags=["模型配置"])


@router.get("")
def list_models(
    model_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: SysUser = Depends(require_permissions("model:list")),
    db: Session = Depends(get_db),
):
    """模型配置分页列表。"""
    items, total = ai_model_service.list_models(
        db, model_type=model_type, keyword=keyword, page=page, page_size=page_size
    )
    return ok(page_result(items, total, page, page_size))


@router.post("")
def create_model(
    data: AIModelCreate,
    operator: SysUser = Depends(require_permissions("model:create")),
    db: Session = Depends(get_db),
):
    """新增模型配置（api_key Fernet 加密入库）。"""
    return ok(ai_model_service.create_model(db, data, operator), message="新增成功")


@router.put("/{model_id}")
def update_model(
    model_id: int,
    data: AIModelUpdate,
    operator: SysUser = Depends(require_permissions("model:update")),
    db: Session = Depends(get_db),
):
    """编辑模型配置（api_key 留空保持原值）。"""
    return ok(ai_model_service.update_model(db, model_id, data, operator), message="保存成功")


@router.delete("/{model_id}")
def delete_model(
    model_id: int,
    operator: SysUser = Depends(require_permissions("model:delete")),
    db: Session = Depends(get_db),
):
    """软删除模型配置。"""
    ai_model_service.delete_model(db, model_id, operator)
    return ok(message="删除成功")


@router.post("/{model_id}/default")
def set_default(
    model_id: int,
    operator: SysUser = Depends(require_permissions("model:update")),
    db: Session = Depends(get_db),
):
    """设为同类型唯一默认。"""
    return ok(ai_model_service.set_default(db, model_id, operator), message="已设为默认")


@router.post("/{model_id}/test")
def test_model(
    model_id: int,
    operator: SysUser = Depends(require_permissions("model:test")),
    db: Session = Depends(get_db),
):
    """连通性测试：llm 最小对话 / embedding 维度探针。"""
    return ok(ai_model_service.test_model(db, model_id, operator))
