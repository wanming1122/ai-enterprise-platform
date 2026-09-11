"""登录认证链路集成测试：登录、失败计数、停用账号、刷新轮换、退出黑名单。"""
from app.models.user import SysUser
from app.services.auth_service import _ip_fail, pwd_context


def _clear_ip_fail():
    """清空进程内 IP 失败计数，避免跨用例累积误触发 IP 锁定（MAX_IP_FAIL=20）。"""
    _ip_fail.clear()


def _create_user(db, username: str, *, password: str = "Passw0rd123", status: int = 1) -> SysUser:
    user = SysUser(
        username=username,
        password_hash=pwd_context.hash(password),
        nickname=username,
        status=status,
    )
    db.add(user)
    db.commit()
    return user


def test_login_success_returns_tokens_and_menus(client, db_session):
    _create_user(db_session, "t_login_ok")
    res = client.post("/api/v1/auth/login", json={"username": "t_login_ok", "password": "Passw0rd123"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["access_token"] and data["refresh_token"]
    assert data["user"]["username"] == "t_login_ok"
    assert isinstance(data["menus"], list) and isinstance(data["permissions"], list)


def test_login_wrong_password_401(client, db_session):
    _create_user(db_session, "t_login_bad")
    res = client.post("/api/v1/auth/login", json={"username": "t_login_bad", "password": "wrong-pass"})
    assert res.status_code == 401


def test_login_unknown_user_401(client):
    res = client.post("/api/v1/auth/login", json={"username": "no_such_user_xyz", "password": "whatever1"})
    assert res.status_code == 401


def test_login_locks_after_five_failures_with_structured_detail(client, db_session):
    _clear_ip_fail()
    _create_user(db_session, "t_lock_user")
    # 前 4 次失败：无锁定详情
    for _ in range(4):
        res = client.post("/api/v1/auth/login", json={"username": "t_lock_user", "password": "bad-pass"})
        assert res.status_code == 401
        assert res.json()["data"] is None
    # 第 5 次失败：触发锁定，data 携带结构化锁定信息供前端倒计时
    res = client.post("/api/v1/auth/login", json={"username": "t_lock_user", "password": "bad-pass"})
    assert res.status_code == 401
    body = res.json()
    assert "锁定" in body["message"]
    assert body["data"]["locked"] is True
    assert body["data"]["remain_seconds"] == 900


def test_login_locked_account_403_returns_remain_seconds(client, db_session):
    _clear_ip_fail()
    _create_user(db_session, "t_lock_403")
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": "t_lock_403", "password": "bad-pass"})
    # 锁定期内即使密码正确也拒绝，并返回剩余秒数
    res = client.post("/api/v1/auth/login", json={"username": "t_lock_403", "password": "Passw0rd123"})
    assert res.status_code == 403
    body = res.json()
    assert "锁定" in body["message"]
    assert body["data"]["locked"] is True
    assert 0 < body["data"]["remain_seconds"] <= 900


def test_login_disabled_account_403(client, db_session):
    _create_user(db_session, "t_login_disabled", status=0)
    res = client.post("/api/v1/auth/login", json={"username": "t_login_disabled", "password": "Passw0rd123"})
    assert res.status_code == 403
    assert "停用" in res.json()["message"] or "停用" in res.text


def test_refresh_rotation_invalidates_old_token(client, db_session):
    _create_user(db_session, "t_refresh")
    login = client.post("/api/v1/auth/login", json={"username": "t_refresh", "password": "Passw0rd123"}).json()["data"]

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert refresh.status_code == 200
    new_pair = refresh.json()["data"]
    assert new_pair["refresh_token"] != login["refresh_token"]

    # 旧刷新令牌已轮换作废
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert replay.status_code == 401

    # 新令牌可用，且 /me 可访问
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_pair['access_token']}"})
    assert me.status_code == 200
    assert me.json()["data"]["user"]["username"] == "t_refresh"


def test_logout_blacklists_refresh_token(client, db_session):
    _create_user(db_session, "t_logout")
    login = client.post("/api/v1/auth/login", json={"username": "t_logout", "password": "Passw0rd123"}).json()["data"]

    out = client.post("/api/v1/auth/logout", json={"refresh_token": login["refresh_token"]})
    assert out.status_code == 200

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert replay.status_code == 401


def test_protected_endpoint_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code in (401, 403)
