"""企业工具 MCP Server：把 AI 助手已有的 3 个只读工具对外暴露为 MCP（Model Context Protocol）服务。

对外提供（Claude Desktop / Cursor 等任意 MCP 客户端可复用）：
  - retrieve(query)          检索企业知识库文档片段（BM25+向量混合检索 + CRAG 校正）
  - nl2sql(question)         自然语言查询业务库（仅 SELECT、白名单表、强制 LIMIT 的四层安全校验）
  - server_admin(action,path) 只读探查服务器（沙箱限定项目目录；可在 .env 用 MCP_ENABLE_SERVER_ADMIN=false 关闭）

安全模型：
  - 三个工具全部只读；stdio 本地信任模式（与 Claude Desktop 一致：谁能启动本进程谁可用）
  - nl2sql 不写 nl2sql_record（该表 user_id 外键绑定产品内提问人），改写 sys_log 审计（source=mcp）
  - 关闭方式：.env 加 MCP_ENABLE_SERVER_ADMIN=false

客户端配置（Claude Desktop claude_desktop_config.json / Cursor mcp.json 同构）：
  {
    "mcpServers": {
      "enterprise-tools": {
        "command": "D:/agent学习/demo/backend/.venv/Scripts/python.exe",
        "args": ["D:/agent学习/demo/backend/mcp_server.py"]
      }
    }
  }

运行：backend/.venv/Scripts/python.exe mcp_server.py   （stdio 传输，前台阻塞运行）
"""
import json

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.kb import KBKnowledgeBase
from app.services import kb_rag_service, nl2sql_service, server_admin_service
from app.services.operation_log_service import write_log

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("enterprise-tools")


@mcp.tool()
def retrieve(query: str) -> str:
    """检索企业知识库文档片段（公司制度、流程、文档内容等）。

    Args:
        query: 检索关键词或问题改写
    """
    from fastapi import HTTPException

    db = SessionLocal()
    try:
        kb_ids = list(db.scalars(select(KBKnowledgeBase.id).where(KBKnowledgeBase.status == 1)).all())
        if not kb_ids:
            return "当前没有启用的知识库，无法检索。"
        try:
            results, used = kb_rag_service.retrieve_with_crag(db, query=query, kb_ids=kb_ids, top_k=6)
        except HTTPException as exc:
            return f"知识库检索暂不可用：{exc.detail}"
        if not results:
            return "知识库中未检索到相关资料。"
        lines = [f"实际检索词：{used}", ""]
        for i, c in enumerate(results, start=1):
            lines.append(
                f"[{i}] 文件：{c.get('file_name')}｜标题路径：{c.get('title_path')}"
                f"｜页码：{c.get('page')}｜相似度：{c.get('similarity')}\n{str(c.get('content') or '')[:500]}"
            )
        return "\n\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def nl2sql(question: str) -> str:
    """自然语言查询业务数据库实时数据（product/sys_user/att_record/sal_payroll 四表，支持 JOIN）。

    Args:
        question: 自然语言数据问题，如"库存大于100的产品按价格倒序"
    """
    from fastapi import HTTPException

    try:
        sql = nl2sql_service.generate_sql(question)  # 内含四层安全校验，不合法 422
        rows, ms = nl2sql_service.execute_readonly(sql)
    except HTTPException as exc:
        return f"查询失败：{exc.detail}"
    # 审计：MCP 外部调用无系统用户，不写 nl2sql_record（user_id 外键绑定提问人），
    # 改写 sys_log（operation_log 的 user_id 允许为空）
    db = SessionLocal()
    try:
        write_log(db, module="NL2SQL", action="MCP执行SQL",
                  params={"source": "mcp", "question": question[:200], "sql": sql,
                          "rows": len(rows), "ms": ms}, result=1)
    finally:
        db.close()
    return json.dumps(
        {"sql": sql, "row_count": len(rows), "elapsed_ms": ms, "rows": rows[:50]},
        ensure_ascii=False, default=str,
    )


@mcp.tool()
def server_admin(action: str, path: str | None = None) -> str:
    """只读探查服务器状态：system_info 系统信息 / disk 磁盘 / process 进程 / network 网络 / file_list 目录浏览 / file_read 读取项目内文本文件。

    Args:
        action: 要执行的只读探查动作
        path: file_list/file_read 的项目内相对路径，缺省为项目根目录
    """
    if not settings.MCP_ENABLE_SERVER_ADMIN:
        return "server_admin 工具已在服务端关闭（.env: MCP_ENABLE_SERVER_ADMIN=false）。"
    return server_admin_service.run_action(action, {"path": path} if path else None)


if __name__ == "__main__":
    mcp.run()  # stdio 传输：由 MCP 客户端（Claude Desktop / Cursor 等）作为子进程拉起
