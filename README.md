# 企业管理系统（FastAPI + React + MySQL 8）

一个前后端分离的企业管理系统，覆盖**组织与权限、考勤薪资、个人中心、RAG 知识库、AI 智能中心、工作台看板、系统管理**七大板块，重点实现 RBAC 动态菜单权限体系与「知识库检索 + NL2SQL + Agent 工具调用」的 AI 能力。

- **后端**：107 个 Python 模块（21 个路由模块 / 28 个服务 / 20 个模型 / 21 个入参 schema），30 张表由 22 个 Alembic 迁移版本管理
- **前端**：78 个源文件（34 个视图组件文件、22 个接口模块、5 个通用组件），动态菜单驱动路由 + 页面级代码分包
- **测试**：后端 13 个测试文件 140 个用例（pytest，独立测试库零污染）；前端 5 个测试文件 18 个用例（vitest）

---

## 一、技术栈

| 层次 | 技术选型 | 说明 |
| --- | --- | --- |
| 后端框架 | FastAPI + Uvicorn | 自带 `/docs` 接口文档、Pydantic 入参校验、依赖注入体系 |
| ORM / 数据库 | SQLAlchemy 2.0（同步）+ PyMySQL + Alembic | 表结构演进全部走迁移脚本，无手工 SQL |
| 数据库 | MySQL 8（utf8mb4） | 关系型主库，避免中文乱码 |
| 认证 | PyJWT + Passlib(bcrypt) | JWT 双 Token（access 30 分钟 / refresh 7 天） |
| 加密 | cryptography（Fernet） | 模型 api_key 加密入库，掩码回显 |
| 表格处理 | pandas + openpyxl | 考勤/用户 Excel 导入导出 |
| 文档解析 | pdfplumber + python-docx | 知识库 PDF / Word 解析 |
| 向量与检索 | Chroma（PersistentClient）+ jieba | 向量库嵌入式持久化；BM25 手写 Okapi + RRF 融合 + rerank |
| Agent 编排 | LangGraph + langchain-core | `StateGraph` 编排 agent ⇄ tools → generate |
| LLM 客户端 | httpx（手写 OpenAI 兼容调用） | 流式解析 `data:` SSE，分离 reasoning_content 与 content |
| 前端框架 | React 18 + TypeScript 6 + Vite 8 | 路由级懒加载，入口包 gzip 104 KB |
| UI | antd 5 + @ant-design/icons | ConfigProvider 开启 cssVar，支持明暗主题联动 |
| 状态管理 | zustand 5 | 单 store 管理 token / 用户 / 菜单 / 权限 |
| 请求 | axios 1.20 + 原生 fetch（SSE） | 统一拦截器 + 双 Token 无感刷新；流式请求走 fetch |
| 可视化 | echarts 6 | 工作台看板图表，随路由延迟加载 |
| Markdown | react-markdown + remark-gfm + highlight.js | AI 回复与知识库问答渲染，代码块高亮可复制 |
| 工程化 | oxlint / vitest / tsc -b | lint、单元测试、类型检查 |

> 设计约束：不引入 Redis / Docker / 消息队列。实训规模下进程内方案（限流计数、令牌作废表）即可满足，换来更低的运维与理解成本。

---

## 二、功能模块

| 模块 | 能力 |
| --- | --- |
| 认证与安全 | 账号密码登录（连续失败 5 次锁定 15 分钟、IP+账号维度限流、防账号枚举）、双 Token 无感刷新与轮换、退出即作废、找回密码（验证码 bcrypt 存储、10 分钟 TTL、账号/IP 双维度限流、试错 5 次作废、SMTP 可选+演示回显兜底）、操作审计日志 |
| 组织管理 | 员工 / 部门 / 职位 / 角色 / 菜单 五组 CRUD，注册审批（登录页公开申请 → 管理员审批 → 自动激活建号绑角色），入职邀请（生成链接 → 外部注册自动绑部门角色 → 全程状态日志），启停、排序、Excel 导入导出、按钮级权限 |
| 考勤薪资 | 电子考勤表 Excel 导入（脏数据容错、逐行错误报告、同日覆盖）、手动补录、考勤规则维护；按月生成工资单（基本工资 + 考勤增减 + 手动奖惩）、确认 / 发放状态机、明细追溯 |
| 个人中心 | 我的信息 / 我的考勤 / 我的工资（严格仅本人数据）、头像上传、修改密码（强制改密守卫）、偏好设置（默认首页 / 侧边栏默认折叠 / 站内消息 / 主题 / 默认模型 / AI 记忆开关） |
| RAG 知识库 | 知识库与文件管理（后缀白名单 + 文件头魔数校验 + SHA256 去重）、pdf/docx/md/txt 解析切片（500/80，标题路径溯源）、向量化入库、混合检索（向量 + BM25 → RRF → rerank）、CRAG 自校正检索、SSE 流式问答带 `[n]` 引用、检索调试、索引重建 |
| AI 智能中心 | 模型配置（llm/embedding/rerank 三类，Fernet 加密、连通性测试、默认切换）；NL2SQL（自然语言 → SQL → 人工审核 → 只读执行 → 历史，四层安全校验）；AI 助手（LangGraph Agent：知识库检索 + NL2SQL + 服务器只读探查三个工具，SSE 流式、深度思考、会话持久化与置顶、历史分页、长期记忆、图片多模态问答） |
| 工作台 | 统计卡片（在职人数 / 部门 / 职位 / 考勤异常 / 工资单）+ echarts 图表（部门人数含未分配部门、职位分布、考勤状态、薪资趋势、人员结构），单聚合接口一次返回 |
| 系统管理 | 操作日志（全局审计：登录、权限拦截、关键业务操作，支持关键字/模块/结果/时间筛选）、系统参数配置（预置键可编辑不可增删）、数据字典（类型 + 字典项两级维护） |

---

## 三、目录结构

```
demo/
├── backend/                          # FastAPI 后端
│   ├── alembic/
│   │   ├── env.py                    #   从 settings.database_url 取连接串，target_metadata = Base.metadata
│   │   └── versions/                 #   22 个迁移版本（M0→M15），含初始账号/菜单/权限/字典/考勤规则播种
│   ├── app/
│   │   ├── core/                     #   核心基础设施
│   │   │   ├── config.py             #     Settings（读 .env）、弱 JWT 密钥随机兜底
│   │   │   ├── security.py           #     JWT 双 Token 签发/校验、刷新令牌轮换与宽限作废
│   │   │   └── deps.py               #     get_current_user / require_permissions / 数据范围控制
│   │   ├── db/
│   │   │   ├── base.py               #     DeclarativeBase
│   │   │   └── session.py            #     engine / SessionLocal / get_db 依赖
│   │   ├── models/                   #   30 张表的 SQLAlchemy 模型（sys_* / att_* / sal_* / kb_* / ai_* ...）
│   │   ├── routers/                  #   21 个路由模块（路由声明 + 权限声明）
│   │   ├── schemas/                  #   21 个 Pydantic 入参模块（common.py 提供 PhoneStr）
│   │   ├── services/                 #   28 个业务服务（认证/菜单/考勤/薪资/知识库/AI/NL2SQL...）
│   │   ├── utils/                    #   统一响应、分页、Fernet 加密、Excel、手机号校验
│   │   └── main.py                   #   应用入口：CORS、计时中间件、全局异常处理、路由注册
│   ├── tests/                        #   13 个测试文件 140 用例（独立库 enterprise_test + savepoint 回滚）
│   ├── media/                        #   上传文件存储（media/kb/{kb_id}/{uuid}.{ext}）
│   ├── data/chroma/                  #   Chroma 向量库持久化目录
│   ├── mcp_server.py                 #   MCP Server：把 retrieve / nl2sql / server_admin 对外暴露给 MCP 客户端
│   ├── alembic.ini / pytest.ini
│   ├── requirements.txt / requirements-dev.txt
│   └── .env / .env.example
├── frontend/                         # React 前端
│   ├── src/
│   │   ├── api/
│   │   │   ├── request.ts            #   axios 封装：令牌存取、双实例、401 无感刷新重放、统一错误、Blob 下载
│   │   │   ├── sse.ts                #   SSE 流式基座（fetch + ReadableStream 手工解析）
│   │   │   └── *.ts                  #   22 个业务接口模块（user/department/role/kb/nl2sql/aiChat...）
│   │   ├── components/               #   Breadcrumb / ForceChangePassword / HasPermission / MarkdownText / ThinkingIndicator
│   │   ├── layouts/MainLayout.tsx    #   主布局：侧栏菜单 + 顶栏 + 内容区局部 Suspense + 强制改密守卫
│   │   ├── router/
│   │   │   ├── index.tsx             #   动态菜单驱动路由 + 守卫 + 首页偏好跳转
│   │   │   └── viewLoaders.ts        #   页面懒加载注册表（单一事实来源）+ 空闲预载
│   │   ├── stores/user.ts            #   zustand 单 store（token/userInfo/menus/permissions/initialized）
│   │   ├── types/index.ts            #   全局类型
│   │   ├── utils/                    #   image.ts（图片压缩 Data URL）、phone.ts
│   │   ├── views/                    #   34 个视图组件（页面及页面内子组件），覆盖 dashboard/org/attendance/salary/profile/ai/log/settings/login/invite
│   │   ├── App.tsx                   #   根组件：ConfigProvider 主题 + 会话初始化
│   │   └── main.tsx                  #   入口（StrictMode）
│   ├── vite.config.ts                #   端口 5173，/api 代理到 127.0.0.1:8000，@ 别名
│   └── package.json
├── start-all.bat / stop-all.bat      # 一键启动 / 停止（幂等：端口占用则跳过）
├── README.md
├── CHANGELOG.md / 项目总结.md / 开发文档.md
└── Bug审计与修复记录.md / 前端CRUD测试报告.md / 组织架构模块设计方案.md
```

---

## 四、关键模块说明

### 4.1 后端分层与调用关系

```
routers（路由 + require_permissions 权限声明）
   ↓ 依赖注入 get_db / get_current_user
services（业务逻辑，唯一写审计日志的地方）
   ↓
models（SQLAlchemy 表）        schemas（Pydantic 入参）
        utils（response / page / crypto / excel / phone）
        alembic（迁移 + 播种）
```

**核心约定**：统一响应 `{code, message, data}`（`code=0` 成功）；分页 `{list, total, page, page_size}`；业务失败统一 `raise HTTPException`；删除一律软删除（`status=2`）。

### 4.2 认证与权限

- `app/core/security.py`：双 Token 签发；刷新时**轮换**（旧 jti 记入进程内作废表，30 秒宽限期内仍可重放以容忍多标签页并发刷新，超期拒绝；退出登录 `grace=0` 立即作废）。
- `app/services/auth_service.py`：登录限流按 **IP + 账号** 分桶（账号 5 次失败锁 15 分钟、同 IP+账号 20 次锁 15 分钟），锁定到期自动清零失败计数；账号不存在时执行恒定哑哈希校验，拉平响应时间防用户名枚举。
- `app/core/deps.py`：`require_permissions("user:list")` 依赖工厂——超管豁免、无权限 403 并写「权限拦截」审计；`get_data_scope` / `apply_data_scope` 实现「仅本人 / 本部门 / 全部」三档数据范围（薪资、考勤已接入）。
- 前端 `HasPermission` 组件只管按钮显隐，**权限判定以后端为准**。

### 4.3 横切关注点

- **统一响应与异常**（`app/main.py`）：`StarletteHTTPException`（结构化 detail 透传到 `data`）、`RequestValidationError` → 422（含 Pydantic 自定义校验器不可序列化的降级处理）、`IntegrityError` → 422、兜底 `Exception` → 500。
- **请求计时**：纯 ASGI 中间件把请求起点写入 ContextVar，`write_log` 自动计算接口耗时。
- **审计日志**（`operation_log_service.write_log`）：记录操作人、模块、动作、方法、路径、参数、IP、结果、耗时。

### 4.4 前端请求层与路由

- **`api/request.ts`**：`request`（带拦截器）/ `raw`（裸实例，仅用于刷新，避免 401 循环）双实例；`refreshAccessToken` 单例让并发 401 只刷新一次；`RefreshError` 区分「令牌确实失效（401/403）」与「网络不可达（保留令牌）」，避免后端重启或断网误踢用户；`handleSessionExpired` 去重，保证并发 401 只提示一次、只跳转一次。
- **`api/sse.ts`**：原生 fetch + ReadableStream 手工解析 SSE，供 AI 助手与知识库问答复用；401 时复用同一刷新单例。
- **动态路由**（`router/index.tsx` + `viewLoaders.ts`）：后端菜单下发 `component` 串（如 `views/org/user/index`）→ `viewMap` 映射到 `React.lazy` 组件递归生成 `<Route>`；目录节点只作分组，按钮节点不下发；未注册组件落占位页。`preloadComponent` / `preloadPages` 在空闲时分批预载页面 chunk。
- **会话恢复**（`stores/user.ts`）：启动时用本地令牌请求 `/auth/me`；仅 401/403 清空令牌，网络错误保留令牌并重试 3 次，避免「一键启动后端未就绪」被误判为未登录。

### 4.5 AI 链路

- **NL2SQL 四层纵深防御**：① prompt 硬约束（仅一条 SELECT、表白名单、恒带 `status!=2`、`LIMIT<=100`、不带库前缀）；② 生成与执行共用纯函数 `validate_and_normalize_sql`（**先剥离字符串字面量**再做黑名单扫描，避免 `LIKE '%delete%'` 误杀）；③ 会话级 `SET SESSION TRANSACTION READ ONLY`；④ 独立连接池 + 5 秒超时 + `MAX_EXECUTION_TIME`。
- **RAG 检索**：向量检索 + 手写 BM25（jieba 分词）双路 → RRF 融合 → 可选 rerank → CRAG 充分性评估与查询改写；软删文件在 MySQL 侧二次过滤保证不可见；`_bm25_cache` 以 `frozenset(kb_ids)` 为键、按「切片总数 + 最大 id」自动失效。
- **AI 助手**：`StateGraph` 编排 `agent ⇄ tools → generate`，工具为 `retrieve` / `nl2sql` / `server_admin`；`stream_mode=["custom","values"]` 一次流式调用同时拿增量事件与终态 state；流内异常一律转为 `error` 事件下发；`server_admin` 有文件沙箱与权限双门控，全部 action 只读。

---

## 五、依赖与调用关系

### 后端 `backend/requirements.txt`

| 分类 | 依赖 |
| --- | --- |
| Web | `fastapi>=0.110`、`uvicorn[standard]>=0.29`、`python-multipart>=0.0.9` |
| ORM / DB | `sqlalchemy>=2.0`、`pymysql>=1.1`、`alembic>=1.13`、`aiosqlite>=0.20` |
| 校验 / 配置 | `pydantic>=2.6`、`pydantic-settings>=2.2` |
| 认证 | `pyjwt>=2.8`、`passlib[bcrypt]>=1.7.4`、`bcrypt==4.0.1`（固定版本） |
| 加密 | `cryptography>=42.0` |
| 表格 | `pandas>=2.2`、`openpyxl>=3.1` |
| 文档解析 | `pdfplumber>=0.11`、`python-docx>=1.1` |
| 向量 / Agent | `chromadb>=0.5`、`langgraph>=0.2`、`langchain-core>=0.3`、`langchain-openai>=0.2` |
| 分词 / HTTP | `jieba>=0.42`、`httpx>=0.27` |

开发依赖（`requirements-dev.txt`）：`pytest>=8.0`。

### 前端 `frontend/package.json`

运行时：`react` / `react-dom` 18.3、`react-router-dom` 6.30、`antd` 5.29、`@ant-design/icons` 5.6、`zustand` 5.0、`axios` 1.20、`echarts` 6.1、`dayjs` 1.11、`react-markdown` 10.1、`remark-gfm` 4.0、`highlight.js` 11.12。

开发：`vite` 8.2、`typescript` 6.0、`@vitejs/plugin-react` 6.1、`vitest` 5.0、`jsdom` 30、`@testing-library/react` 16.3、`oxlint` 1.79。

脚本：`dev`（vite）、`build`（`tsc -b && vite build`）、`lint`（oxlint）、`test`（vitest run）、`preview`。

### 模块依赖方向

```
前端 views ─→ api/* ─→ request.ts（拦截器/令牌）─→ /api/v1/*
                                   └─→ sse.ts（流式）
前端 router ← stores/user ← api/request
后端 routers ─→ services ─→ models
                     └─→ utils（response/page/crypto/excel）
services/auth_service ─→ core/security（令牌）
services/* ─→ operation_log_service（审计）
services/kb_rag_service ─→ Chroma（data/chroma）+ MySQL（kb_chunk 双写）
services/ai_chat_service ─→ llm_client ─→ 外部 LLM API
```

---

## 六、快速启动

环境要求：**Python 3.12+、Node.js 18+、MySQL 8**。

### 方式一（推荐）：一键脚本

双击根目录 `start-all.bat`：自动检查 MySQL 3306 端口 → 后端窗口先执行 `alembic upgrade head` 同步迁移再启动 Uvicorn（含 `--reload`）→ 前端窗口启动 Vite → 延时后自动打开浏览器。脚本幂等：端口已占用则跳过并提示。`stop-all.bat` 按端口一键停止两个服务。

### 方式二：手动分步

**1) 初始化数据库**

```sql
CREATE DATABASE enterprise CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

**2) 后端**

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt        # Linux/Mac: .venv/bin/pip install -r requirements.txt
copy .env.example .env                                # 填写 DB / JWT_SECRET / FERNET_KEY
.venv\Scripts\python -m alembic upgrade head          # 建 30 张表并播种初始数据
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

接口文档：http://127.0.0.1:8000/docs

**3) 前端**

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173，/api 代理到 127.0.0.1:8000
```

**4) AI 功能配置**（NL2SQL / 知识库问答 / AI 助手）

登录后进入「AI 智能中心 → 模型配置」添加并设为默认：

- **生成模型**（llm）：OpenAI 兼容接口，用于 SQL 生成、多轮改写与 AI 助手
- **向量模型**（embedding）：用于知识库切片向量化与检索
- **重排模型**（rerank，可选）：未配置时自动降级为 RRF 融合序

api_key 经 Fernet 对称加密入库（密钥为 `.env` 的 `FERNET_KEY`，生成命令见 `.env.example`），列表只回显掩码。未配置默认模型时回退 `.env` 中的 `MIMO_*` / `ZHIPU_API_KEY`。

**5) MCP Server（可选）**

```bash
cd backend
.venv\Scripts\python mcp_server.py      # stdio 传输，暴露 retrieve / nl2sql / server_admin 三个只读工具
```

---

## 七、预置账号与演示数据

| 账号 | 密码 | 说明 |
| --- | --- | --- |
| `admin` | `admin123456` | 超级管理员，迁移自动播种，拥有全部权限 |
| `emp_zhang` / `emp_li` / `emp_wang` / `emp_zhao` / `emp_liu` / `reg_emp` | `Demo@123456` | 演示员工账号，用于验证菜单差异（可问答但无知识库管理 / NL2SQL / 模型配置权限）与个人中心数据隔离 |
| Excel 导入初始密码 | `admin123456` | 用户管理的员工批量导入默认密码 |

迁移完成后自动预置：**3 个角色**（超级管理员 / 普通管理员 / 普通员工）、**93 条菜单**、**84 个权限标识**及其授权关系、6 个部门 / 6 个职位（演示）、考勤规则、字典与系统参数。全新初始化时业务表为空，可通过页面录入或 Excel 导入。

---

## 八、自动化测试

```bash
# 后端：13 个文件 140 个用例
cd backend
.venv/Scripts/pip.exe install -r requirements-dev.txt
.venv/Scripts/python.exe -m pytest tests/ -v

# 前端：5 个文件 18 个用例（含类型检查与 lint）
cd frontend
npm test
npm run build
npm run lint
```

后端测试覆盖：NL2SQL 安全校验与生成提示词（只读 / 限表 / 限行 / 防注入 / 字面量剥离）、登录认证（限流锁定 / 到期清零 / 分桶限流 / 刷新轮换宽限期 / 退出作废）、找回密码（发码限流 / 试错限次 / 过期 / 重置）、工资单计算（三项构成 / 确认锁定）、AI 会话与路由 / 上下文窗口 / 长期记忆、知识库解析、工作台看板、手机号校验与唯一性。

**测试隔离**：自动使用独立库 `enterprise_test`（不存在时自动创建并迁移播种）；用例级 savepoint 回滚，服务层的 `db.commit()` 被收敛为 savepoint 释放，**不污染开发库**。

前端测试覆盖：SSE 块解析、`streamAIChat` / `streamKBChat` 事件映射、Markdown 代码块增强、AI 对话思考面板与错误重试。

---

## 九、开发约定与安全要点

**全局约定**

- 统一响应 `{code, message, data}`；分页 `{list, total, page, page_size}`
- 删除一律软删除（`status=2`），列表恒过滤；部分唯一键在软删时改写释放（如用户名/手机号），允许重建
- 管理接口必须挂 `Depends(require_permissions("模块:动作"))`；关键操作必须写 `sys_log`
- 金额全程 `DECIMAL(10,2)`，服务层用 `Decimal` 累加，杜绝 float
- 密钥只进 `.env`，不硬编码

**安全设计清单**

| 攻击面 | 防线 |
| --- | --- |
| 密码 | bcrypt 哈希；连续失败 5 次锁 15 分钟；防账号枚举（统一错误文案 + 恒定哑哈希） |
| 令牌 | 双 Token；刷新轮换 + 旧 jti 作废（30 秒宽限期）；退出立即失效；前端并发刷新单例 |
| 找回密码 | 验证码 bcrypt 存储、10 分钟 TTL、账号 + IP 双维度限流、试错 5 次作废 |
| SQL 注入（NL2SQL） | prompt 约束 → 字面量剥离 + 黑名单正则 + 表白名单 + LIMIT 归一化 → 会话 READ ONLY → 独立只读连接 5 秒超时（四层） |
| 越权 | 后端依赖注入校验 + 403 审计留痕；数据范围控制；前端组件只管显隐 |
| 文件上传 | 后缀白名单 + 文件头魔数校验 + 50MB 上限 + 同库 SHA256 去重 |
| LLM 触达系统 | `server_admin` 文件沙箱 + action 白名单 + 权限双门控；图片 Data URL 正则白名单（png/jpg/webp） |
| 密钥 | Fernet 加密入库、掩码回显、`.env` 管理 |

---

## 十、里程碑对照

```
M0-T1/T2   仓库与前后端骨架
M1-T1~T5   组织与权限表、认证、用户/部门管理、角色与菜单管理
M2-T1~T5   职位、考勤、薪资管理及个人中心
M3-T1~T4   RAG 知识库（表 / 解析入库 / 检索问答 / 前端页面）
M4-T1~T3   AI 智能中心（模型配置 / NL2SQL / AI 助手 LangGraph）
M5-T1~T3   工作台看板、全量回归、交付物
M6-T1~T7   找回密码、AI 图片多模态、个人偏好与主题、一键脚本、服务器管理工具、性能分包、自动化测试
M7~M15     AI 会话置顶、长期记忆、上下文窗口、用量统计、数据范围、软删唯一键释放、
           邀请链路修复、知识库菜单权限修复、手机号唯一约束
```

更详细的技术选型理由、难点与解决方案见 [`项目总结.md`](./项目总结.md)。
