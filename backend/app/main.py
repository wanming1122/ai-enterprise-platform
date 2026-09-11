"""FastAPI 应用入口：CORS、请求计时、统一响应、全局异常处理、健康检查与路由注册。"""
import json
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers import ai, ai_model, approval, auth, attendance, config, dashboard, department, dict, kb, log, menu, nl2sql, permission, position, product, profile, role, salary, user, invitation
from app.services.operation_log_service import clear_request_start, mark_request_start
from app.utils.response import error, ok

app = FastAPI(
    title="企业管理系统 API",
    description="企业管理系统：组织架构（认证/RBAC/动态菜单）+ 业务模块 + AI 智能中心 + RAG 知识库",
    version="0.1.0",
)


class RequestTimingMiddleware:
    """纯 ASGI 计时中间件：请求入口记录起点到 ContextVar，
    审计日志 write_log 据此自动计算接口耗时（无请求上下文时保持 0）。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        mark_request_start()
        try:
            await self.app(scope, receive, send)
        finally:
            clear_request_start()


# 注意：纯 ASGI 中间件不经过 BaseHTTPMiddleware 的子任务派生，
# ContextVar 的写入对下游路由/依赖直接可见。
app.add_middleware(RequestTimingMiddleware)

# CORS：放行前端 Vite 开发服务（5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 全局统一响应与异常处理 ----------

def _code_of(status_code: int) -> int:
    """业务 code 与 HTTP 状态码对齐：401/403/422/500。"""
    return status_code


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # 结构化 detail（如登录锁定的 {message, locked, remain_seconds}）原样透传到 data，
    # 供前端渲染倒计时；普通字符串 detail 保持向后兼容。
    detail = exc.detail
    if isinstance(detail, Mapping):
        return JSONResponse(
            status_code=exc.status_code,
            content=error(
                code=_code_of(exc.status_code),
                message=str(detail.get("message") or "请求失败"),
                data=detail,
            ),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=error(code=_code_of(exc.status_code), message=str(detail)),
    )


def _json_safe_validation_errors(errors: list) -> list:
    """Pydantic 校验错误转 JSON 安全结构。

    Pydantic v2 的自定义校验器（如 PhoneStr）抛 ValueError 时，errors() 的 ctx
    会携带异常实例，直接序列化会 TypeError 并被兜底处理器放大成 500；
    这里逐字段做可序列化探测，不可序列化的降级为字符串。

    注意：本模块已导入名为 dict 的 router 模块（见上方 import），
    故不可用内置 dict 做 isinstance 判断，改用 Mapping。
    """

    def safe(value):
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except (TypeError, ValueError):
            return str(value)

    out = []
    for err in errors:
        item = {k: safe(v) for k, v in err.items()}
        ctx = err.get("ctx")
        if isinstance(ctx, Mapping):
            item["ctx"] = {k: safe(v) for k, v in ctx.items()}
        out.append(item)
    return out


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error(code=422, message="参数错误", data=_json_safe_validation_errors(exc.errors())),
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """唯一约束/外键冲突（并发注册同名、悬空外键等）转 422，不再落 500。"""
    return JSONResponse(
        status_code=422,
        content=error(code=422, message="数据冲突：唯一性或关联校验失败，请检查后重试"),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=error(code=500, message="服务器内部错误"))


# ---------- 路由 ----------

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(department.router)
app.include_router(position.router)
app.include_router(role.router)
app.include_router(menu.router)
app.include_router(permission.router)
app.include_router(attendance.router)
app.include_router(attendance.rule_router)
app.include_router(salary.router)
app.include_router(profile.router)
app.include_router(kb.router)
app.include_router(ai_model.router)
app.include_router(product.router)
app.include_router(nl2sql.router)
app.include_router(ai.router)
app.include_router(dashboard.router)
app.include_router(log.router)
app.include_router(approval.router)
app.include_router(invitation.router)
app.include_router(config.router)
app.include_router(dict.router)

@app.get("/api/v1/health", tags=["系统"])
def health():
    """健康检查。"""
    return ok(message="ok")