"""系统参数配置路由（M5 补齐）：预置项查询与更新。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permissions
from app.db.session import get_db
from app.models.user import SysUser
from app.schemas.config import ConfigUpdateIn
from app.services import config_service
from app.utils.response import ok

router = APIRouter(prefix="/api/v1/configs", tags=["系统配置"])


@router.get("")
def list_configs(
    _: SysUser = Depends(require_permissions("config:list")),
    db: Session = Depends(get_db),
):
    """配置项列表（预置项，不支持新增/删除）。"""
    return ok(config_service.list_configs(db))


@router.put("/{config_id}")
def update_config(
    config_id: int,
    data: ConfigUpdateIn,
    operator: SysUser = Depends(require_permissions("config:update")),
    db: Session = Depends(get_db),
):
    """更新配置值/说明。"""
    return ok(config_service.update_config(db, config_id, data, operator), message="保存成功")
