"""FastAPI 应用入口：CORS、统一响应、全局异常处理、健康检查与路由注册。"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.response import error, ok

app = FastAPI(
    title="企业管理系统 API",
    description="企业管理系统：组织架构（认证/RBAC/动态菜单）+ 业务模块 + AI 智能中心 + RAG 知识库",
    version="0.1.0",
)

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
    return JSONResponse(
        status_code=exc.status_code,
        content=error(code=_code_of(exc.status_code), message=str(exc.detail)),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error(code=422, message="参数错误", data=exc.errors()),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=error(code=500, message="服务器内部错误"))


# ---------- 路由 ----------

@app.get("/api/v1/health", tags=["系统"])
def health():
    """健康检查。"""
    return ok(message="ok")