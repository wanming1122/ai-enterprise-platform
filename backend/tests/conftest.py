"""测试基建：独立测试库 enterprise_test + 用例级 savepoint 回滚，绝不污染开发库。

- 会话级：测试库不存在时自动创建，并跑 alembic 迁移到最新（含 admin 账号/菜单/考勤规则等种子数据）
- 用例级：在单个连接事务内执行，服务层的 commit 收敛到 savepoint，结束统一回滚，不留任何数据
- 隔离：conftest 顶层先设 DB_NAME 环境变量再导入 app，settings 与 alembic 全部指向测试库
"""
import os
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

# 必须先于 import app 设置：pydantic-settings 中环境变量优先级高于 .env
os.environ["DB_NAME"] = "enterprise_test"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """创建 enterprise_test 并迁移到最新（幂等：库与表已存在时跳过建表仅校验版本）。"""
    server_engine = create_engine(settings.database_url.rsplit("/", 1)[0])
    with server_engine.connect() as conn:
        conn.execute(text(
            "CREATE DATABASE IF NOT EXISTS enterprise_test "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
        conn.commit()
    server_engine.dispose()

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def engine(_test_database):
    return create_engine(settings.database_url, pool_pre_ping=True)


@pytest.fixture()
def db_session(engine):
    """用例级回滚会话：直接传给 service 层函数做单元/集成断言。"""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    """HTTP 接口测试：get_db 覆盖为用例回滚会话。"""

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def admin_headers(client):
    """预置超管 admin / admin123456 的鉴权头。"""
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123456"})
    assert res.status_code == 200, res.text
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
