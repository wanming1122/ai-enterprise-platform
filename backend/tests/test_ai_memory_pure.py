"""AI 助手长期记忆纯函数测试：不触库、不调 LLM（提取/去重/清洗/估算/注入格式化）。"""
import pytest

from app.services.ai_memory_service import (
    estimate_tokens,
    format_injection,
    merge_decision,
    parse_extraction,
    sanitize_memory,
)


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_cjk_one_per_char(self):
        assert estimate_tokens("你好世界") == 4

    def test_ascii_four_chars_per_token(self):
        assert estimate_tokens("abcdefgh") == 2  # 8/4

    def test_mixed(self):
        # 2 CJK + 8 ascii → 2 + 2
        assert estimate_tokens("你好abcdefgh") == 4


class TestSanitizeMemory:
    def test_normal_content_kept(self):
        assert sanitize_memory(" 用户是财务部的员工 ") == "用户是财务部的员工"

    def test_phone_number_rejected(self):
        assert sanitize_memory("我的手机号是13812345678请记住") is None

    def test_id_card_rejected(self):
        assert sanitize_memory("身份证号11010119900307889X请保存") is None

    def test_api_key_rejected(self):
        assert sanitize_memory("我的key是sk-abcdefgh12345678请记住") is None

    def test_empty_rejected(self):
        assert sanitize_memory("   ") is None

    def test_overlong_clipped(self):
        assert len(sanitize_memory("长" * 500)) == 300


class TestParseExtraction:
    def test_plain_json_array(self):
        items = parse_extraction('[{"type":"preference","content":"用户偏好表格回答"}]')
        assert items == [{"type": "preference", "content": "用户偏好表格回答"}]

    def test_fenced_json(self):
        raw = '```json\n[{"type":"fact","content":"用户是财务部"}]\n```'
        assert parse_extraction(raw) == [{"type": "fact", "content": "用户是财务部"}]

    def test_prose_wrapped(self):
        raw = '提取结果如下：[{"type":"fact","content":"用户是技术部"}] 以上。'
        assert parse_extraction(raw) == [{"type": "fact", "content": "用户是技术部"}]

    def test_invalid_returns_empty(self):
        assert parse_extraction("这不是JSON") == []
        assert parse_extraction("") == []
        assert parse_extraction("[]") == []

    def test_sensitive_item_dropped(self):
        items = parse_extraction('[{"type":"fact","content":"手机号13912345678"},{"type":"fact","content":"用户是人事部"}]')
        assert [i["content"] for i in items] == ["用户是人事部"]

    def test_type_normalized(self):
        items = parse_extraction('[{"type":"whatever","content":"用户在测试环境工作"}]')
        assert items[0]["type"] == "fact"


class TestMergeDecision:
    def test_exact_duplicate_skips(self):
        existing = [{"id": 1, "content": "用户是财务部", "similarity": 0.5}]
        assert merge_decision("用户是财务部", existing) == ("skip", 1)
        assert merge_decision("用户是财务部 ", existing) == ("skip", 1)  # 忽略大小写与空白
        assert merge_decision("用户是财务部", [{"id": 1, "content": "用户是财务部", "similarity": 0.5}]) == ("skip", 1)

    def test_high_similarity_updates(self):
        existing = [{"id": 7, "content": "用户是财务部的", "similarity": 0.95}]
        assert merge_decision("用户在财务部工作", existing) == ("update", 7)

    def test_dissimilar_creates_new(self):
        existing = [{"id": 7, "content": "用户是财务部的", "similarity": 0.4}]
        assert merge_decision("用户偏好深色主题", existing) == ("new", None)

    def test_no_existing_creates_new(self):
        assert merge_decision("任意内容", []) == ("new", None)


class TestFormatInjection:
    def test_empty_returns_empty(self):
        assert format_injection([]) == ""

    def test_contains_all_memories(self):
        out = format_injection([
            {"content": "用户是财务部"},
            {"content": "用户偏好表格回答"},
        ])
        assert "- 用户是财务部" in out
        assert "- 用户偏好表格回答" in out
        assert "长期记忆" in out

    def test_budget_cap(self):
        memories = [{"content": "x" * 500} for _ in range(10)]
        out = format_injection(memories, max_chars=800)
        assert len(out) <= 800 + 80  # 预算 + 固定前缀
