"""中国大陆手机号校验单元测试（纯函数 + Pydantic 集成，不触库）。"""
import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.common import PhoneStr
from app.utils.phone import (
    CODE_EMPTY,
    CODE_ILLEGAL_CHARS,
    CODE_LENGTH,
    CODE_PREFIX,
    check_phone,
    is_valid_phone,
    normalize_phone,
)


# ---------- 合法输入（含各类分隔符，应被清洗） ----------

@pytest.mark.parametrize("raw, expected", [
    ("13800001234", "13800001234"),
    ("138 0000 1234", "13800001234"),
    ("138-0000-1234", "13800001234"),
    ("138–0000—1234", "13800001234"),          # en dash / em dash
    ("  13800001234  ", "13800001234"),
    ("138.0000.1234", "13800001234"),
    ("138　0000　1234", "13800001234"),         # 全角空格
    ("13000000000", "13000000000"),            # 第二位下界 3
    ("19900001234", "19900001234"),            # 第二位上界 9
])
def test_valid_phone(raw, expected):
    r = check_phone(raw)
    assert r.valid is True
    assert r.code == "" and r.message == ""
    assert r.normalized == expected


# ---------- 空输入 ----------

@pytest.mark.parametrize("raw", [None, "", "   ", "\u3000", " - – "])
def test_empty_input(raw):
    r = check_phone(raw)
    assert r.valid is False
    assert r.code == CODE_EMPTY
    assert r.message == "请输入手机号"


# ---------- 含非数字字符 ----------

@pytest.mark.parametrize("raw", [
    "1380000123a", "138*0000*1234", "138+0000+1234",
    "１３８００００１２３４",  # 全角数字（isdigit 为真但非 ASCII，须拒绝）
])
def test_illegal_chars(raw):
    r = check_phone(raw)
    assert r.valid is False
    assert r.code == CODE_ILLEGAL_CHARS
    assert r.message == "手机号只能包含数字（可用空格或短横线分隔）"


# ---------- 长度不符 ----------

@pytest.mark.parametrize("raw", ["1380000123", "138000012345", "1", "138-000-1234"])
def test_invalid_length(raw):
    r = check_phone(raw)
    assert r.valid is False
    assert r.code == CODE_LENGTH
    assert r.message == "手机号需为 11 位数字"


# ---------- 号段不合法 ----------

@pytest.mark.parametrize("raw", [
    "23800001234",  # 首位不是 1
    "10800001234",  # 第二位 0
    "11800001234",  # 第二位 1
    "12800001234",  # 第二位 2
])
def test_invalid_prefix(raw):
    r = check_phone(raw)
    assert r.valid is False
    assert r.code == CODE_PREFIX
    assert r.message == "手机号号段不合法（需以 1 开头，第二位为 3-9）"


# ---------- 错误优先级：空 → 非数字 → 长度 → 号段 ----------

def test_error_priority():
    assert check_phone("").code == CODE_EMPTY
    assert check_phone("abc").code == CODE_ILLEGAL_CHARS       # 非数字优先于长度
    assert check_phone("12345abc").code == CODE_ILLEGAL_CHARS
    assert check_phone("12345").code == CODE_LENGTH            # 纯数字但长度不足
    assert check_phone("12345678901").code == CODE_PREFIX      # 11 位纯数字但号段错


# ---------- 辅助函数 ----------

def test_normalize_phone():
    assert normalize_phone(" 138-0000-1234 ") == "13800001234"
    assert normalize_phone(None) == ""
    assert normalize_phone("138 0000 1234") == "13800001234"
    assert normalize_phone("abc") == "abc"  # 只清洗分隔符，不做合法性判断


def test_is_valid_phone():
    assert is_valid_phone("138-0000-1234") is True
    assert is_valid_phone("12345") is False
    assert is_valid_phone(None) is False


# ---------- Pydantic 集成（PhoneStr：清洗后入库，失败转 422 文案） ----------

class _PhoneModel(BaseModel):
    phone: PhoneStr


def test_schema_normalizes_on_valid():
    assert _PhoneModel(phone="138-0000-1234").phone == "13800001234"
    assert _PhoneModel(phone=" 138 0000 1234 ").phone == "13800001234"


@pytest.mark.parametrize("bad, keyword", [
    ("", "请输入手机号"),
    ("1380000123", "11 位"),
    ("12800001234", "号段不合法"),
    ("1380000123a", "只能包含数字"),
])
def test_schema_rejects_with_clear_message(bad, keyword):
    with pytest.raises(ValidationError) as exc:
        _PhoneModel(phone=bad)
    assert keyword in str(exc.value)


def test_schema_requires_phone():
    with pytest.raises(ValidationError):
        _PhoneModel()  # 缺字段 → 必填校验
