# 企业管理系统实训项目

基于 FastAPI + React + MySQL 8 的企业管理系统，覆盖组织与权限（RBAC/动态菜单）、考勤薪资业务、RAG 知识库、AI 智能中心（模型配置 / NL2SQL / AI 助手）与工作台数据看板。

- 后端：FastAPI + SQLAlchemy 2.0（sync, pymysql）+ Alembic + PyJWT + Passlib(bcrypt)
- 前端：React 18 + TypeScript + antd 5 + zustand + axios + echarts（Vite 构建）
- 数据库：MySQL 8（utf8mb4）
- AI：MiMo-V2.5（OpenAI 兼容接口，推理/工具调用）+ 智谱 embedding-3（向量化）+ Chroma（向量库）+ LangGraph（Agent 编排）

## 功能模块

| 模块 | 内容 |
| --- | --- |
| 认证与安全 | 账号密码登录（连续失败 5 次锁定 15 分钟）、双 Token 无感刷新与轮换、找回密码（验证码哈希存储、10 分钟有效、账号/IP 双维度限流、试错 5 次作废；演示环境验证码直接回显）、操作审计日志 |
| 组织管理 | 员工/部门/职位/角色/菜单 CRUD、注册审批（登录页公开申请→审批通过自动激活建号绑角色）、入职邀请（生成链接→外部注册自动绑部门角色，全程状态日志）、启停、排序、Excel 导入导出、RBAC 按钮级权限 |
| 考勤薪资 | 电子考勤表导入、按月生成工资单（基本工资 + 考勤增减 + 手动奖惩）、确认/发放 |
| 个人中心 | 我的信息 / 我的考勤 / 我的工资（仅本人数据）、偏好设置（默认首页/侧边栏默认折叠/站内消息提醒） |
| RAG 知识库 | 知识库管理、pdf/docx/md 解析切片向量化入库、SSE 流式问答带 [n] 引用、检索调试 |
| AI 智能中心 | 模型配置（Fernet 加密/连通性测试）、NL2SQL（自然语言生成 SQL→人工审核→只读执行→查询历史）、AI 助手（LangGraph Agent：知识库检索 + NL2SQL 工具，流式输出、深度思考、会话持久化、图片多模态问答，模型不支持视觉时自动降级纯文本） |
| 工作台 | 统计卡片（在职人数/部门/职位/考勤异常/工资单）+ echarts 图表（部门人数含未分配部门） |
| 操作日志 | 全局审计日志分页查询（登录/越权拦截/关键业务操作） |
| 系统配置 | 全局参数配置（系统名称/欢迎语等，键预置可编辑）、字典类型与字典项两级维护 |



## 快速启动

环境要求：Python 3.12+、Node.js 18+、MySQL 8。

**方式一（推荐）：双击根目录 `start-all.bat`** —— 自动检查 MySQL、同步数据库迁移（alembic upgrade head）、在新窗口分别启动后端（含 `--reload` 热重载）与前端，完成后自动打开浏览器；`stop-all.bat` 按端口一键停止两个服务。以下为手动分步启动。

### 1. 初始化数据库

```sql
CREATE DATABASE enterprise CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 后端（backend/）

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt      # Windows
# Linux/Mac: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 复制环境变量模板并填写数据库连接、JWT_SECRET、FERNET_KEY 等
copy .env.example .env                              # Linux/Mac: cp .env.example .env

# 数据库迁移：创建全部 29 张表并播种初始账号/菜单/权限
.venv\Scripts\python -m alembic upgrade head

# 启动（http://127.0.0.1:8000，接口文档 /docs）
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

迁移链自 M0 至 M5 逐级执行，完成后自动预置：

- 初始账号 **admin / admin123456**（超级管理员，bcrypt 种子写入迁移，首启即可登录）
- 三个角色（超级管理员/普通管理员/普通员工）、87 条菜单、82 个权限标识及其授权关系

### 3. 前端（frontend/）

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 代理到 127.0.0.1:8000
```

### 4. AI 功能配置（NL2SQL / 知识库问答 / AI 助手）

登录后在「AI智能中心 → 模型配置」添加并设为默认：

- **生成模型**（llm）：OpenAI 兼容接口（如 MiMo-V2.5），填 base_url 与 api_key，用于 SQL 生成、多轮改写与 AI 助手
- **向量模型**（embedding）：如智谱 embedding-3，用于知识库切片向量化与检索

api_key 经 Fernet 对称加密入库（密钥为 .env 的 `FERNET_KEY`，生成命令见 `.env.example`）。未配置默认模型时自动回退 `.env` 中的 `MIMO_*` / `ZHIPU_API_KEY`。

> 数据库初始化说明：全量表结构均由 Alembic 迁移管理（`alembic upgrade head` 一键构建），无手工 SQL 脚本；降级可 `alembic downgrade <revision>`。

## 自动化测试

```bash
cd backend
.venv/Scripts/pip.exe install -r requirements-dev.txt   # 安装 pytest（仅需一次）
.venv/Scripts/python.exe -m pytest tests/ -v
```

覆盖四条核心链路共 36 个用例：NL2SQL 安全校验（只读/限表/限行/防注入）、登录认证（限流锁定/刷新轮换/退出黑名单）、工资单计算（三项构成/确认锁定）、找回密码（发码限流/试错限次/过期/重置）。
测试自动使用独立库 `enterprise_test`（不存在时自动创建并迁移播种），用例内所有写入收敛到 savepoint、结束统一回滚，**不污染开发库**。

## 预置账号

| 账号 | 密码 | 角色 | 说明 |
| --- | --- | --- | --- |
| admin | admin123456 | 超级管理员 | 迁移自动播种，全部权限 |
| emp_zhang / emp_li / emp_wang / emp_zhao / emp_liu / reg_emp | Demo@123456 | 普通员工 | 演示数据员工，用于验证菜单差异（含 AI助手入口：可问答，无知识库管理/NL2SQL/模型配置权限）、个人中心数据隔离 |
| 用户导入 | admin123456 | — | 员工管理 Excel 导入的默认初始密码 |

演示库已含示例数据：6 个部门、6 个职位、在职员工与本月考勤/工资单、产品数据、AI 会话记录。全新初始化则业务表为空，可通过各页面录入或 Excel 导入。

## 目录说明

```
├── backend/                     # FastAPI 后端
│   ├── alembic/                 #   数据库迁移（含菜单/权限/初始账号播种）
│   ├── app/
│   │   ├── core/                #   配置（.env）、安全、依赖注入（登录态/权限校验）
│   │   ├── db/                  #   引擎与会话
│   │   ├── models/              #   SQLAlchemy 模型（sys_* / att_* / sal_* / kb_* / product / nl2sql_record / ai_*）
│   │   ├── routers/             #   路由（auth/user/department/.../kb/nl2sql/ai/dashboard/log）
│   │   ├── schemas/             #   Pydantic 入参
│   │   ├── services/            #   业务服务（auth/menu/attendance/salary/kb_rag/kb_chat/ai_chat/nl2sql...）
│   │   └── utils/               #   统一响应、分页、Fernet 加密、Excel
│   ├── media/                   #   上传文件存储（.gitignore）
│   └── requirements.txt
├── frontend/                    # React 前端
│   └── src/
│       ├── api/                 #   接口封装（axios 统一拦截 + SSE 流式）
│       ├── components/          #   HasPermission 权限组件
│       ├── layouts/             #   主布局（动态菜单侧栏）
│       ├── router/              #   动态路由（后端菜单 component 串 → viewMap）
│       ├── stores/              #   zustand（token/用户/菜单/权限）
│       └── views/               #   页面（org/attendance/salary/profile/ai/dashboard/log）
├── 开发文档.md / 组织架构模块设计方案.md / 实训成果物要求.md
└── README.md
```

## 约定与要点

- 统一响应 `{code, message, data}`，分页 `{list, total, page, page_size}`；业务失败 `raise HTTPException`（401/403/404/422）。
- 权限：管理接口 `Depends(require_permissions("模块:动作"))` 校验，无权限 403 并写审计；前端按钮用 `<HasPermission code="xxx">` 控制显隐。
- 删除一律软删除（status=2），列表不再显示。
- NL2SQL 安全：仅一条 SELECT、仅 product 表、强制 LIMIT≤100、黑名单关键词，生成入库前与执行前双重校验；独立只读连接执行（5 秒超时）。
- 会话/消息/审计留痕：ai_conversation / ai_message / nl2sql_record / sys_log。

## 提交历史（里程碑对照）

```
M0-T1/M0-T2  仓库与后端骨架、前端骨架
M1-T1~T5     组织与权限表、认证、用户/部门管理、角色与菜单管理
M2-T1~T5     职位、考勤、薪资管理及个人中心
M3-T1~T4     RAG 知识库（表/解析入库/检索问答/前端页面）
M4-T1~T3     AI智能中心（模型配置/NL2SQL/AI助手 LangGraph）
M5-T1~T3     工作台看板、全量回归、交付物
M6-T1~T4     找回密码、AI助手图片多模态、个人偏好设置、一键启动/停止脚本
```
