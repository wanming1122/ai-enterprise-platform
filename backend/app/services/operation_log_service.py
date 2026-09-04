"""操作审计日志服务：统一写入 sys_log，全系统关键操作复用。"""
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.log import SysLog


def write_log(
    db: Session,
    *,
    user_id: int | None = None,
    username: str | None = None,
    module: str = "",
    action: str = "",
    method: str = "",
    path: str = "",
    params: Any = None,
    ip: str = "",
    device: str = "",
    result: int = 1,
    error_message: str | None = None,
    duration_ms: int = 0,
) -> SysLog:
    """写入一条操作日志。params 可为 dict/list/str，非字符串自动 JSON 序列化。"""
    param_text = None
    if params is not None:
        param_text = (
            params
            if isinstance(params, str)
            else json.dumps(params, ensure_ascii=False, default=str)
        )
    log = SysLog(
        user_id=user_id,
        username=username,
        module=module,
        action=action,
        method=method,
        path=path,
        params=param_text,
        ip=ip,
        device=device,
        result=result,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    db.add(log)
    db.commit()
    return log
