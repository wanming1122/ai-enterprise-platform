"""工资单计算链路集成测试：三项构成（基本工资+考勤增减+手动奖惩）、确认后锁定。"""
from datetime import date

from app.models.attendance import AttRecord, AttRule
from app.models.department import SysDepartment
from app.models.position import SysPosition
from app.models.salary import SalAdjustment, SalPayroll
from app.models.user import SysUser
from app.schemas.salary import SalaryGenerate
from app.services.auth_service import pwd_context
from app.services.salary_service import confirm_payroll, generate_payrolls

YM = "2030-05"  # 远期空月份，避开种子演示数据


def _setup_employee(db, username: str = "t_salary"):
    """建 部门+职位(基本工资5000)+在职员工，返回 (user, position)。"""
    dept = SysDepartment(name=f"测试部{username}", status=1)
    db.add(dept)
    db.flush()
    position = SysPosition(
        name=f"测试岗{username}", code=f"T_{username}", level=1,
        base_salary=5000, description="测试职位", status=1,
    )
    db.add(position)
    db.flush()
    user = SysUser(
        username=username, password_hash=pwd_context.hash("Passw0rd123"),
        nickname=username, status=1, department_id=dept.id, position_id=position.id,
    )
    db.add(user)
    db.commit()
    return user, position


def _upsert_rule(db, status_key: str, adjust_type: int, amount):
    """考勤规则按 status_key 唯一：存在则改额度，不存在新建。"""
    rule = db.query(AttRule).filter(AttRule.status_key == status_key).one_or_none()
    if rule is None:
        db.add(AttRule(status_key=status_key, adjust_type=adjust_type, amount=amount, enabled=1))
    else:
        rule.adjust_type = adjust_type
        rule.amount = amount
        rule.enabled = 1
    db.commit()


def _add_attendance(db, user, dept_id: int, day: int, status: str):
    db.add(AttRecord(user_id=user.id, dept_id=dept_id, att_date=date(2030, 5, day), status=status, source=2))
    db.commit()


def test_payroll_three_components(client, db_session):
    """迟到2次(-50×2) + 旷工1天(-200) + 手动奖励100：5000 - 300 + 100 = 4800。"""
    _upsert_rule(db_session, "late", adjust_type=2, amount=50)
    _upsert_rule(db_session, "absent", adjust_type=2, amount=200)
    user, _ = _setup_employee(db_session, "t_sal_calc")
    _add_attendance(db_session, user, user.department_id, 8, "late")
    _add_attendance(db_session, user, user.department_id, 9, "late")
    _add_attendance(db_session, user, user.department_id, 10, "absent")
    db_session.add(SalAdjustment(
        user_id=user.id, adjust_type=1, amount=100, reason="月度优秀", year_month=YM, operator_id=user.id,
    ))
    db_session.commit()

    admin = db_session.query(SysUser).filter_by(username="admin").one()
    result = generate_payrolls(db_session, SalaryGenerate(year_month=YM, user_ids=[user.id]), admin)
    assert result["generated"] == 1

    payroll = db_session.query(SalPayroll).filter_by(user_id=user.id, year_month=YM).one()
    assert float(payroll.base_salary) == 5000
    assert float(payroll.attendance_adjust) == -300
    assert float(payroll.manual_adjust) == 100
    assert float(payroll.total_salary) == 4800
    assert payroll.status == 0  # 草稿


def test_confirmed_payroll_locked_on_recalculate(client, db_session):
    """已确认的工资单重算时锁定不覆盖。"""
    _upsert_rule(db_session, "late", adjust_type=2, amount=50)
    user, _ = _setup_employee(db_session, "t_sal_lock")
    _add_attendance(db_session, user, user.department_id, 8, "late")
    admin = db_session.query(SysUser).filter_by(username="admin").one()

    generate_payrolls(db_session, SalaryGenerate(year_month=YM, user_ids=[user.id]), admin)
    payroll = db_session.query(SalPayroll).filter_by(user_id=user.id, year_month=YM).one()
    confirm_payroll(db_session, payroll.id, admin)
    db_session.refresh(payroll)
    assert payroll.status == 1

    # 修改考勤再重算：已确认记录不重算
    _add_attendance(db_session, user, user.department_id, 11, "absent")
    result = generate_payrolls(db_session, SalaryGenerate(year_month=YM, user_ids=[user.id]), admin)
    db_session.refresh(payroll)
    assert float(payroll.total_salary) == 4950  # 仍为 5000 - 50
    assert result["locked"] >= 1
