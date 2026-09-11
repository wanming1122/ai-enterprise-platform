"""用户手机号唯一性约束集成测试：新增/编辑查重、检查接口、软删释放。

依赖 conftest 的 client + admin_headers + db_session（用例级回滚，不污染测试库）。
测试库由 M1 种子提供部门 1、职位 1，作为创建用户的必填关联项。
"""


def _create(client, headers, username: str, phone: str):
    return client.post(
        "/api/v1/users",
        json={
            "username": username,
            "password": "Passw0rd123",
            "real_name": username,
            "phone": phone,
            "department_id": 1,
            "position_id": 1,
            "role_ids": [],
        },
        headers=headers,
    )


def test_create_duplicate_phone_rejected(client, db_session, admin_headers):
    r1 = _create(client, admin_headers, "t_phone_a", "13800000001")
    assert r1.status_code == 200, r1.text
    r2 = _create(client, admin_headers, "t_phone_b", "13800000001")
    assert r2.status_code == 422
    assert "手机号已被使用" in r2.json()["message"]


def test_update_duplicate_phone_rejected_self_ok(client, db_session, admin_headers):
    a = _create(client, admin_headers, "t_phone_c", "13800000002").json()["data"]
    b = _create(client, admin_headers, "t_phone_d", "13800000003").json()["data"]

    # 改为他人已占用手机号 → 422
    res = client.put(
        f"/api/v1/users/{b['id']}",
        json={"phone": "13800000002", "department_id": 1, "position_id": 1},
        headers=admin_headers,
    )
    assert res.status_code == 422
    assert "手机号已被使用" in res.json()["message"]

    # 保持自身手机号不变 → 200（排除自身）
    res = client.put(
        f"/api/v1/users/{b['id']}",
        json={"phone": "13800000003", "department_id": 1, "position_id": 1},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text


def test_check_phone_endpoint(client, db_session, admin_headers):
    u = _create(client, admin_headers, "t_phone_e", "13800000004").json()["data"]
    res = client.get("/api/v1/users/check-phone?phone=13800000004", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["data"]["exists"] is True

    res = client.get("/api/v1/users/check-phone?phone=13800000005", headers=admin_headers)
    assert res.json()["data"]["exists"] is False

    # 排除占用者自身 → 视为可用
    res = client.get(
        f"/api/v1/users/check-phone?phone=13800000004&exclude_id={u['id']}", headers=admin_headers
    )
    assert res.json()["data"]["exists"] is False


def test_soft_delete_releases_phone(client, db_session, admin_headers):
    u = _create(client, admin_headers, "t_phone_f", "13800000006").json()["data"]
    res = client.delete(f"/api/v1/users/{u['id']}", headers=admin_headers)
    assert res.status_code == 200

    # 软删后手机号可被新用户复用
    res = _create(client, admin_headers, "t_phone_g", "13800000006")
    assert res.status_code == 200, res.text
