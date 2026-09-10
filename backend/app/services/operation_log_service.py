"""操作审计日志服务：统一写入 sys_log，全系统关键操作复用。

耗时来源：main.py 的 RequestTimingMiddleware 在请求入口把起点写入 ContextVar，
write_log 未显式传入 duration_ms 时自动按"当前时刻 - 请求起点"计算（毫秒）；
后台任务等无请求上下文的场景保持 0。
"""
import json
import time
from contextvars import ContextVar
from typing import Any

from sqlalchemy.orm import Session

from app.models.log import SysLog

# 请求起点（perf_counter 秒），由计时中间件在请求入口设置
_request_started_at: ContextVar[float | None] = ContextVar("request_started_at", default=None)


def mark_request_start() -> None:
    """计时中间件在请求入口调用：记录请求起点。"""
    _request_started_at.set(time.perf_counter())


def clear_request_start() -> None:
    """请求结束后清理，避免复用线程/事件循环时读到陈旧起点。"""
    _request_started_at.set(None)


def _current_duration_ms() -> int:
    started = _request_started_at.get()
    if started is None:
        return 0
    return int((time.perf_counter() - started) * 1000)


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
    duration_ms: int | None = None,
) -> SysLog:
    """写入一条操作日志。params 可为 dict/list/str，非字符串自动 JSON 序列化；
    duration_ms 未显式传入时自动取请求开始到当前的时刻差。"""
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
        duration_ms=duration_ms if duration_ms is not None else _current_duration_ms(),
    )
    db.add(log)
    db.commit()
    return log
