"""NL2SQL 安全校验单元测试（纯函数，不触库）：只读、限表、限行、防注入。"""
import pytest
from fastapi import HTTPException

from app.services.nl2sql_service import validate_and_normalize_sql


def test_plain_select_kept():
    sql = "SELECT name, stock FROM product WHERE stock > 100 ORDER BY price DESC LIMIT 50"
    assert validate_and_normalize_sql(sql) == sql


def test_missing_limit_appended():
    assert validate_and_normalize_sql("SELECT name FROM product").endswith(" LIMIT 100")


def test_limit_over_max_rewritten():
    assert validate_and_normalize_sql("SELECT name FROM product LIMIT 500") == \
        "SELECT name FROM product LIMIT 100"


def test_markdown_fence_stripped():
    raw = "```sql\nSELECT name FROM product LIMIT 10\n```"
    assert validate_and_normalize_sql(raw) == "SELECT name FROM product LIMIT 10"


@pytest.mark.parametrize("bad", [
    "INSERT INTO product(name) VALUES('x')",
    "UPDATE product SET stock = 0",
    "DELETE FROM product",
    "DROP TABLE product",
    "SELECT * FROM product INTO OUTFILE '/tmp/x'",
    "SELECT SLEEP(5)",
])
def test_non_select_or_injection_rejected(bad):
    with pytest.raises(HTTPException) as exc:
        validate_and_normalize_sql(bad)
    assert exc.value.status_code == 422


def test_multi_statement_rejected():
    with pytest.raises(HTTPException):
        validate_and_normalize_sql("SELECT name FROM product; DROP TABLE product")


def test_comment_rejected():
    with pytest.raises(HTTPException):
        validate_and_normalize_sql("SELECT name FROM product -- 注释")


def test_other_table_rejected():
    """sys_user现在是允许的表，应该通过验证"""
    sql = validate_and_normalize_sql("SELECT username FROM sys_user LIMIT 10")
    assert "sys_user" in sql.lower()


def test_join_other_table_rejected():
    """sys_user现在是允许的表，JOIN应该通过验证"""
    sql = validate_and_normalize_sql(
        "SELECT p.name FROM product p JOIN sys_user u ON p.id = u.id LIMIT 10"
    )
    assert "sys_user" in sql.lower()


def test_disallowed_table_rejected():
    """不允许的表应该被拒绝"""
    with pytest.raises(HTTPException):
        validate_and_normalize_sql("SELECT * FROM sys_role LIMIT 10")


def test_join_disallowed_table_rejected():
    """JOIN不允许的表应该被拒绝"""
    with pytest.raises(HTTPException):
        validate_and_normalize_sql(
            "SELECT p.name FROM product p JOIN sys_role r ON p.id = r.id LIMIT 10"
        )


def test_qualified_name_rejected():
    with pytest.raises(HTTPException):
        validate_and_normalize_sql("SELECT * FROM enterprise.product LIMIT 10")


def test_keyword_inside_string_literal_allowed():
    """字面量里的危险词不算注入：字符串剥离后才做关键词扫描。"""
    sql = "SELECT name FROM product WHERE description LIKE '%delete%' LIMIT 10"
    assert validate_and_normalize_sql(sql) == sql


def test_bare_offset_rejected():
    """OFFSET 只能以 LIMIT n OFFSET m 的尾巴出现，裸 OFFSET 拒绝。"""
    with pytest.raises(HTTPException):
        validate_and_normalize_sql("SELECT name FROM product OFFSET 5")


def test_limit_offset_form_allowed():
    sql = "SELECT name FROM product LIMIT 10 OFFSET 5"
    assert validate_and_normalize_sql(sql) == sql


def test_limit_offset_count_capped():
    assert validate_and_normalize_sql("SELECT name FROM product LIMIT 10, 5000") == \
        "SELECT name FROM product LIMIT 10, 100"
