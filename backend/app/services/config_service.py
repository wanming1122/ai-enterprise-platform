"""系统参数配置服务（M5 补齐）：预置配置项查询与更新。"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.config import SysConfig
from app.models.user import SysUser
from app.schemas.config import ConfigUpdateIn
from app.services.operation_log_service import write_log


def serialize_config(c: SysConfig) -> dict:
    return {
        "id": c.id,
        "config_key": c.config_key,
        "config_name": c.config_name,
        "config_value": c.config_value,
        "description": c.description,
        "updated_at": c.updated_at.isoformat(),
    }


def list_configs(db: Session) -> list[dict]:
    items = db.scalars(select(SysConfig).order_by(SysConfig.id)).all()
    return [serialize_config(c) for c in items]


def get_config(db: Session, config_id: int) -> SysConfig:
    c = db.get(SysConfig, config_id)
    if c is None:
        raise HTTPException(status_code=404, detail="配置项不存在")
    return c


def update_config(db: Session, config_id: int, data: ConfigUpdateIn, operator: SysUser) -> dict:
    c = get_config(db, config_id)
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(c, field, value)
    db.commit()
    write_log(db, user_id=operator.id, username=operator.username, module="系统配置",
              action="更新配置", params={"id": config_id, "key": c.config_key, **updates}, result=1)
    return serialize_config(c)
