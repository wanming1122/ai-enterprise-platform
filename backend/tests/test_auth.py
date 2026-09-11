"""登录认证链路集成测试：登录、失败计数、停用账号、刷新轮换、退出黑名单。"""
from datetime import datetime, timedelta

from app.core import security
from app.models.user import SysUser
from app.services import auth_service
from app.services.auth_service import MAX_ACCOUNT_FAIL, _ip_fail, pwd_context


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


def test_expired_lock_resets_failed_count(client, db_session):
    """锁定到期后失败计数应清零，避免"解封后再错一次立刻又锁 15 分钟"的粘滞锁。"""
    _clear_ip_fail()
    user = _create_user(db_session, "t_unlock_reset")
    user.failed_login_count = MAX_ACCOUNT_FAIL
    user.locked_until = datetime.now() - timedelta(minutes=1)
    db_session.commit()

    res = client.post("/api/v1/auth/login", json={"username": "t_unlock_reset", "password": "bad-pass"})
    assert res.status_code == 401
    assert res.json()["data"] is None  # 未立即触发新的锁定
    db_session.refresh(user)
    assert user.failed_login_count == 1  # 重新从 1 开始计数
    assert user.locked_until is None


def test_login_limit_is_scoped_per_account(client, db_session, monkeypatch):
    """登录限流按 IP+账号分桶：多账号各自失败不会累计锁死同一 IP（本机开发共用 127.0.0.1）。"""
    monkeypatch.setattr(auth_service, "MAX_IP_FAIL", 6)
    _clear_ip_fail()
    for i in range(2):
        name = f"t_bucket_{i}"
        _create_user(db_session, name)
        for _ in range(5):
            client.post("/api/v1/auth/login", json={"username": name, "password": "bad-pass"})

    # 两个账号合计失败 10 次；若仍按 IP 累计（阈值 6）第三个账号会被连带锁死
    _create_user(db_session, "t_bucket_ok")
    res = client.post("/api/v1/auth/login", json={"username": "t_bucket_ok", "password": "Passw0rd123"})
    assert res.status_code == 200


def test_refresh_rotation_invalidates_old_token(client, db_session):
    """轮换后旧刷新令牌在宽限期内仍可重放（容忍多标签页并发刷新），超出宽限期后作废。"""
    _create_user(db_session, "t_refresh")
    login = client.post("/api/v1/auth/login", json={"username": "t_refresh", "password": "Passw0rd123"}).json()["data"]

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert refresh.status_code == 200
    new_pair = refresh.json()["data"]
    assert new_pair["refresh_token"] != login["refresh_token"]

    # 宽限期内重放：允许（同一浏览器多标签页/并发请求会带上刚被轮换的旧令牌）
    replay_in_grace = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert replay_in_grace.status_code == 200

    # 宽限期结束：把已有作废记录的生效时间提前到过去（模拟超期，避免测试真等 30 秒）
    security._refresh_grace.update({k: 0 for k in list(security._refresh_grace)})
    replay_expired = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert replay_expired.status_code == 401

    # 新令牌可用，且 /me 可访问
    latest_access = replay_in_grace.json()["data"]["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {latest_access}"})
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
