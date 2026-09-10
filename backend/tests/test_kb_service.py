"""知识库管理优化（阶段 1）回归测试：列表批量统计、切片关键词过滤、切片参数变更需重建标记。

均为服务层单元测试：直接构造 kb 记录（跳过 create_kb 的向量维度探测网络调用），
不发真实请求；写入落在用例 savepoint 内，结束统一回滚。
"""
import hashlib

from app.models.kb import KBChunk, KBFile, KBKnowledgeBase
from app.models.user import SysUser
from app.schemas.kb import KBUpdate
from app.services import kb_service


def _admin(db) -> SysUser:
    return db.query(SysUser).filter_by(username="admin").one()


def _kb(db, admin: SysUser, name: str, status: int = 1) -> KBKnowledgeBase:
    kb = KBKnowledgeBase(
        name=name, description=None, embedding_model="test-embed", embedding_dimension=1024,
        chunk_size=500, chunk_overlap=80, collection_name="pending",
        creator_id=admin.id, status=status,
    )
    db.add(kb)
    db.flush()
    kb.collection_name = f"kb_{kb.id}"
    db.commit()
    return kb


def _file(db, kb: KBKnowledgeBase, name: str = "a.md", status: int = 1) -> KBFile:
    f = KBFile(
        kb_id=kb.id, file_name=name, file_type="md", file_size=10,
        content_hash=hashlib.sha256(name.encode()).hexdigest(),
        storage_path=f"kb/{kb.id}/{name}",
        chunk_count=0, parse_status=2, status=status, uploader_id=kb.creator_id,
    )
    db.add(f)
    db.commit()
    return f


def _chunk(db, kb: KBKnowledgeBase, f: KBFile, index: int, content: str, status: int = 1) -> KBChunk:
    c = KBChunk(
        file_id=f.id, kb_id=kb.id, chunk_index=index, content=content,
        char_count=len(content), title_path=None, page=None, chunk_type="text", status=status,
    )
    db.add(c)
    return c


# ---------- A1：列表批量统计 ----------


def test_list_kbs_batch_counts(db_session):
    admin = _admin(db_session)
    kb = _kb(db_session, admin, "A1统计库")
    f = _file(db_session, kb)
    for i in range(3):
        _chunk(db_session, kb, f, i, f"内容{i}")
    db_session.commit()

    items, total = kb_service.list_kbs(db_session, keyword="A1统计库")
    assert total == 1
    row = items[0]
    assert row["file_count"] == 1
    assert row["chunk_count"] == 3


def test_list_kbs_counts_exclude_soft_deleted(db_session):
    """软删的文件不计入 file_count，软删的切片不计入 chunk_count。

    注：既有实现（含原 serialize_kb）统计切片时未 JOIN kb_file，因此「已软删文件」的
    切片仍会被计入 chunk_count —— 这是历史行为，本次批次保持等价不改变语义。
    """
    admin = _admin(db_session)
    kb = _kb(db_session, admin, "A1软删库")
    f_ok = _file(db_session, kb, "ok.md")
    _file(db_session, kb, "del.md", status=2)
    _chunk(db_session, kb, f_ok, 0, "有效切片")
    _chunk(db_session, kb, f_ok, 1, "软删切片", status=2)
    db_session.commit()

    items, _ = kb_service.list_kbs(db_session, keyword="A1软删库")
    row = items[0]
    assert row["file_count"] == 1
    assert row["chunk_count"] == 1


# ---------- B2：切片关键词过滤 ----------


def test_list_chunks_keyword_filter(db_session):
    admin = _admin(db_session)
    kb = _kb(db_session, admin, "B2切片库")
    f = _file(db_session, kb)
    _chunk(db_session, kb, f, 0, "年假制度：入职满一年享受5天年假")
    _chunk(db_session, kb, f, 1, "报销流程：发票需在30天内提交")
    db_session.commit()

    _, total_all = kb_service.list_chunks(db_session, f.id)
    assert total_all == 2

    items, total_hit = kb_service.list_chunks(db_session, f.id, keyword="年假")
    assert total_hit == 1
    assert "年假" in items[0]["content"]

    _, total_miss = kb_service.list_chunks(db_session, f.id, keyword="不存在的关键词")
    assert total_miss == 0


# ---------- B5：切片参数变更需重建标记 ----------


def test_update_kb_requires_rebuild_flag(db_session):
    admin = _admin(db_session)
    kb = _kb(db_session, admin, "B5参数库")

    # 仅改描述：无需重建
    res = kb_service.update_kb(db_session, kb.id, KBUpdate(description="新描述"), admin)
    assert res["requires_rebuild"] is False

    # 改 chunk_size：需重建
    res = kb_service.update_kb(db_session, kb.id, KBUpdate(chunk_size=600), admin)
    assert res["requires_rebuild"] is True
    assert res["chunk_size"] == 600

    # 相同值再提交：不算变化
    res = kb_service.update_kb(db_session, kb.id, KBUpdate(chunk_size=600), admin)
    assert res["requires_rebuild"] is False

    # 改 chunk_overlap：需重建
    res = kb_service.update_kb(db_session, kb.id, KBUpdate(chunk_overlap=100), admin)
    assert res["requires_rebuild"] is True
