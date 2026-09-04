"""分页工具：统一分页返回结构。"""
from typing import Any


def page_result(items: list[Any], total: int, page: int, page_size: int) -> dict:
    return {"list": items, "total": total, "page": page, "page_size": page_size}
