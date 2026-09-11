"""工作台看板按角色区分测试：管理员全量、普通员工脱敏、is_admin_user 判定。"""
from app.models.role import SysRole
from app.models.user import SysUser
from app.models.user_role_relation import SysUserRoleRelation
from app.services import dashboard_service
from app.services.menu_service import is_admin_user, is_super_admin

SENSITIVE_KEYS = (
    "month_abnormal_count",
    "payroll_total",
    "payroll_count",
    "attendance_month_status",
    "attendance_trend",
    "salary_trend",
    "salary_by_dept",
    "headcount_structure",
)


def test_dashboard_admin_full(client, admin_headers):
    """超管看全公司工作台：is_admin=True，敏感字段键完整。"""
    res = client.get("/api/v1/dashboard/summary", headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["is_admin"] is True
    for key in SENSITIVE_KEYS:
        assert key in data


def test_dashboard_employee_masked(db_session):
    """普通员工仅基础看板：is_admin=False，敏感字段为空/零值，不下发。"""
    uid = _bind_role(db_session, "tmp_emp_user", "tmp_emp", 3)
    user = db_session.get(SysUser, uid)
    data = dashboard_service.get_summary(db_session, user)
    assert data["is_admin"] is False
    assert isinstance(data["user_count"], int)
    assert isinstance(data["dept_count"], int)
    assert isinstance(data["position_count"], int)
    assert data["month_abnormal_count"] == 0
    assert data["payroll_total"] == 0
    assert data["payroll_count"] == 0
    assert data["attendance_month_status"] == []
    assert data["attendance_trend"] == []
    assert data["salary_trend"] == []
    assert data["salary_by_dept"] == []
    assert data["headcount_structure"] == {"gender_distribution": [], "age_distribution": []}


def _bind_role(db, username, code, role_type):
    role = SysRole(name=username, code=code, role_type=role_type, status=1)
    user = SysUser(username=username, password_hash="x", nickname=username, status=1)
    db.add_all([role, user])
    db.flush()
    db.add(SysUserRoleRelation(user_id=user.id, role_id=role.id))
    db.commit()
    return user.id


def test_is_admin_user_recognizes_normal_admin(db_session):
    """普通管理员（role_type=2）应判定为管理员，但不是超管。"""
    uid = _bind_role(db_session, "tmp_admin_user", "tmp_admin", 2)
    assert is_admin_user(db_session, uid) is True
    assert is_super_admin(db_session, uid) is False


def test_is_admin_user_false_for_employee(db_session):
    """普通员工（role_type=3）不应判定为管理员。"""
    uid = _bind_role(db_session, "tmp_emp_user", "tmp_emp", 3)
    assert is_admin_user(db_session, uid) is False
