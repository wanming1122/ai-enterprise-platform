# 前端 CRUD 全面测试报告

> 测试方式：静态代码审计（全量） + 浏览器实测（关键路径） + 接口层验证
> 覆盖范围：前端全部 25 个页面及其 api 封装
> 测试时间：2026-09-10
> 环境：MySQL(3306) + 后端 FastAPI(8000) + 前端 Vite(5173)，均本地运行
> 测试账号：`admin/admin123456`（超管）、`emp_zhang/Demo@123456`（普通员工）
> 数据策略：实测统一「新增 → 验证 → 删除」自清理，未留存测试数据
> 交付约定：仅缺陷清单，不修改任何业务代码

---

## 一、结论摘要

| 严重度 | 已实测确认 | 静态审计候选 | 合计 |
| --- | --- | --- | --- |
| 致命 | 0 | 0 | 0 |
| 严重 | 1 | 2 | 3 |
| 一般 | 0 | 13 | 13 |
| 建议 | 0 | 17 | 17 |

- 后端接口与权限校验链路**健康**：CRUD 主流程、越权拦截（403）、数据隔离均正常。
- 前端 CRUD 主流程（以职位为代表）**功能正常**，但存在若干交互与状态管理缺陷。
- 最严重的已确认缺陷：**入职邀请「新建邀请」弹窗的部门/角色下拉为空白、无法选择**（功能不可用）。

---

## 二、已实测确认的缺陷

### DEF-01【严重·已确认】新建邀请弹窗「预设部门 / 预设角色」下拉全空白、无法选择

- **页面/入口**：组织管理 → 入职邀请管理 → 新建邀请
- **定位**：`frontend/src/views/org/invitation/index.tsx:240`、`:243`（数据来源 `:34-35`、`:58-73`）
- **根因**：`<Select options={depts} />`、`<Select options={roles} />` 直接使用 antd `Select.options`，其默认读取 `{ value, label }`；而 `/departments/options` 返回 `{ id, name, parent_id, children }`、`/roles/options` 返回 `{ id, name, code }`，没有 `value/label` → 每项值均为 `undefined`，选项渲染为空。
- **复现步骤**：
  1. admin 登录 → 组织管理 → 入职邀请管理 → 点「新建邀请」
  2. 展开「预设部门」或「预设角色」下拉
  3. 观察：选项为空白行（无文本），选中后 `department_id`/`role_id` 恒为 `undefined`
- **证据**：
  - 接口实测：`roles/options[0] => {"id":1,"name":"超级管理员","code":"super_admin"}`；`departments/options[0] => {"id":1,"name":"技术部","parent_id":null,"children":[]}`
  - 浏览器实测：展开「预设部门」后快照得到 `listbox [ref=e4] → option [ref=e12]、option [ref=e13]`（**option 无任何文本内容**）
- **影响**：邀请无法预设部门/角色，功能不可用。

---

## 三、静态审计候选缺陷

> 以下均为代码级核对结论，尚未逐条动态复现，标注了置信度。

### 严重

#### DEF-02【严重·静态·待特定角色复核】「问答调试」页权限码与接口需求错配
- **定位**：`frontend/src/views/ai/kb/chat/index.tsx`（整页）
- **描述**：该页菜单「问答调试」在后端种子中的权限码是 `kb:chat`（`backend/alembic/versions/e6f5a7b8c9d0_m3_t1_kb_tables.py:33`），但页面已改为复用 AI 助手链路：`aiChatApi.conversations`（`GET /ai/conversations`）、`streamAIChat`（`POST /ai/chat`），这些接口后端要求 `ai:chat`（`backend/app/routers/ai.py:24,50,65`）。同时 `kbApi.conversations / streamKBChat`（要求 `kb:chat`）在前端已无调用。
- **影响**：仅被授予「问答调试」(`kb:chat`) 而未授予「AI助手」(`ai:chat`) 的角色，进入页面后会话列表与发送全部 403；`kb:chat` 权限形同虚设。
- **备注**：admin 与 emp_zhang 均不满足该组合，故本次未动态复现。

#### DEF-03【严重·静态·已确认代码路径】AI 助手「新建会话」状态泄漏，导致跨会话串台
- **定位**：`frontend/src/views/ai/chat/useChat.ts:238-246`（`newConversation`）
- **描述**：`newConversation` 重置了 `currentConvId/messages/oldestServerIdRef`，但**未重置 `hasMoreMessages` 与 `loadOlderRef`**。打开过长会话（`has_more=true`）后点「新建会话」，`hasMoreMessages` 仍为 true，界面显示「加载更早的消息」；点击后执行的是**上一个会话**的 `loadOlderMessages` 闭包，把旧会话的更早消息插入新会话顶部。
- **触发**：打开长会话 → 新建会话 → 发送一条 → 点「加载更早的消息」。

### 一般

| 编号 | 定位 | 问题 | 触发/影响 |
| --- | --- | --- | --- |
| DEF-04 | `views/org/user/index.tsx:273`、`views/org/position/index.tsx:175` | 搜索框回车/点图标只传 `keyword`，`handleSearch` 整体覆盖导致部门/角色/状态筛选被清空 | 先选部门再搜索 → 条件丢失 |
| DEF-05 | `views/org/user/index.tsx:311-314` | 「下载模板」按钮错挂在 `user:export` 下，但后端 `GET /users/template` 要求 `user:import` | 仅有 `user:export` 的用户点击后 403 |
| DEF-06 | `views/org/user/index.tsx:164-168`、`position:109-113`、`role:103-107`、`approval:45-49` | 删除/审批后仅 `loadList()`，未在末页被删空时回退页码 | 末页最后一条删除后停留空页 |
| DEF-07 | `views/org/department/index.tsx:239`、`views/org/menu/index.tsx:258` | `expandable={{ expandedRowKeys }}` 受控但无 `onExpandedRowsChange` 回调 | 树表格展开后无法收起 |
| DEF-08 | `views/org/approval/index.tsx:143-152` | 状态快筛 `setFilters({status})` 整体覆盖，丢失已输入 `keyword` | 先搜索再筛状态 → 关键字丢失 |
| DEF-09 | `views/invite/accept.tsx:32` | 失败时取 `(e as Error).message`，对 HTTP 错误拿到英文 `Request failed with status code 404` | 页面 Result 显示英文，与 toast 中文不一致 |
| DEF-10 | `views/ai/kb/index.tsx:270`、`:319` | 「文件管理」「切片预览」按钮无 `HasPermission`，但对应接口要求 `file:list` | 仅有 `kb:list` 的角色点击后 403 |
| DEF-11 | `views/ai/kb/index.tsx:102-116` | `loadFiles` 无请求序号/取消，快速切换知识库可能被旧响应覆盖 | 显示错误库的文件 |
| DEF-12 | `views/ai/model/index.tsx:105,116,323-342` | 类型切换后隐藏的 `temperature/context_window` 因 `preserve=true` 仍被提交；新增非 llm 时无条件带 `temperature:0.1` | 非 llm 模型携带无关字段 |
| DEF-13 | `views/salary/index.tsx:145` | `handleGenerate` 成功后 `setFilters({year_month})` 整体覆盖，丢弃部门/员工/状态，但内联表单仍显示旧筛选 | 列表与所见筛选不一致 |
| DEF-14 | `views/settings/dict/index.tsx:228-234` | 编辑态 `dict_code` 被 `disabled` 但 pattern 规则仍校验该字段 | 历史编码不合规则时无法保存名称/说明 |
| DEF-15 | `views/attendance/rule/index.tsx:42` | `handleSave` 直接取 `drafts[record.id].adjust_type`，若 `loadRules` 曾失败则 `undefined` | 保存时 `TypeError` |
| DEF-16 | `api/sse.ts:55-65` | SSE 刷新令牌后重放仍 401 时，不清 token/不跳登录（与 axios 拦截器行为不一致） | 用户停在页面反复失败 |

### 建议

| 编号 | 定位 | 问题 |
| --- | --- | --- |
| DEF-17 | `views/org/invitation/index.tsx:97-105` | `navigator.clipboard?.writeText(url).then(...)`：clipboard 为 undefined 时对 undefined 调 `.then` 抛错，被 catch 吞掉 → 无复制也无兜底提示 |
| DEF-18 | `views/org/invitation/index.tsx:144,149,157` | 重发/撤销/删除 `onConfirm` 未返回 Promise → Popconfirm 不 loading，存在重复点击窗口 |
| DEF-19 | `views/invite/accept.tsx:27-34` | 无 token 时 `loading` 初值 true 且未复位 → 无限 Spin |
| DEF-20 | `views/org/role/index.tsx:265-272` | `defaultExpandAll` 对异步 `treeData` 不生效，授权树默认折叠 |
| DEF-21 | `views/dashboard/index.tsx:189-327` | 后四个 EChart `option` 为内联字面量未 `useMemo`，每次 re-render 触发 `setOption` 重绘 |
| DEF-22 | `views/dashboard/index.tsx:34-45` | 看板加载失败无页面级错误态，仅 toast |
| DEF-23 | `views/log/index.tsx:39-60`（及 user/position/role/approval/invitation 列表） | 列表无请求取消/序号，快速切换筛选存在响应竞态 |
| DEF-24 | `views/ai/chat/useChat.ts:632,647` | `renameConversation/togglePin` 失败时页面再 `message.error`，与拦截器提示叠加为两条 toast |
| DEF-25 | `views/ai/chat/MemoryDrawer.tsx:30,110` | 翻页是「追加」而非替换，反复跳页会累积重复数据 |
| DEF-26 | `views/ai/chat/ConversationSidebar.tsx:172-173` | 会话重命名同时绑定 `onPressEnter` 与 `onBlur`，可能双提交 |
| DEF-27 | `views/ai/chat/ConversationSidebar.tsx:319-323` | 搜索态下「加载更多」判据基于已加载总数，语义混乱 |
| DEF-28 | `views/ai/kb/chat/index.tsx:216` | 每轮发送后 `loadConversations(1)` 用第 1 页整体替换，丢弃已加载的后续页 |
| DEF-29 | `views/ai/kb/chat/index.tsx` | 检索调试 `hits` 未在关闭/切换后清理，重开显示上次结果；消息 `key={idx}` |
| DEF-30 | `views/ai/nl2sql/index.tsx:101-102` | 生成后 `setPage(1)` + `loadList()` 双触发，旧页码多请求一次 |
| DEF-31 | `views/ai/nl2sql/history/index.tsx:115,147` | 行 `onClick` 与「详情」按钮均触发 `openDetail` 且未 `stopPropagation`，一次点击执行两次 |
| DEF-32 | `views/profile/info/index.tsx:54,123` | `social_account` 死字段：类型与提交都有，但表单无对应 `Form.Item`，永远 undefined |
| DEF-33 | `views/settings/config/index.tsx:41` | `description: editDesc || undefined` 使描述无法清空 |
| DEF-34 | `views/settings/dict/index.tsx:179` | 启用按钮直接 await，无 `try/catch`、无成功反馈 |
| DEF-35 | `views/attendance/record/index.tsx:147` | 导入成功后未回第 1 页，结果不在当前视图 |
| DEF-36 | `views/salary/index.tsx:172-182` | 确认/发放无 `try/catch` 与 loading，存在 unhandled rejection 与重复点击窗口 |

---

## 四、已排除的误报（动态复核结论）

| 静态疑点 | 复核方式 | 结论 |
| --- | --- | --- |
| 菜单 `Switch` 提交布尔 `visible/is_external` 导致 422 | 接口实测：`POST /menus` 传 `visible:true` → **HTTP 200**，后端已转 `visible:1` | **误报**，pydantic 宽松模式可接受 bool→int |
| 「编辑职位」弹窗点保存后 OK 永久 loading | 显式点击 OK → `PUT /positions/18` **200 OK** + 「编辑成功」+ 弹窗关闭 | **工具假象**（agent-browser `fill` 命令触发的中间态），**非应用 bug** |

---

## 五、正常项确认（实测通过）

| 项目 | 结论 |
| --- | --- |
| 登录流程（admin） | 通过：进入工作台，6 个菜单、83 个权限，看板数据正常 |
| 职位 CRUD 全流程 | 通过：创建成功（列表 6→7）、编辑回填正确（名称/编码/工资，编码 disabled）、更新成功、删除成功（总数回 7→6） |
| 表单必填校验 | 通过：空表单提交提示「请输入职位名称/职位编码/基本工资」 |
| 列表刷新与总数 | 通过：增改删后列表与 `共 N 条` 同步更新 |
| 越权拦截（emp_zhang） | 通过：`/users` 403、`/logs` 403、`/kb/conversations` 403（无 kb:chat）、`/ai/conversations` 200 |
| 个人数据隔离 | 通过：员工账号仅 3 菜单/5 权限，无管理接口入口 |

---

## 六、遗留与建议

1. **优先修复顺序建议**：DEF-01（功能不可用） → DEF-02/DEF-03（严重） → DEF-04/05/06/07/08（高频交互）。
2. **本次未覆盖的深层场景**（建议补充）：
   - 分页大数据量下的「末页删除回收」（DEF-06）需造数据复现；
   - AI 助手流式问答期间的会话切换/删除（DEF-03、DEF-25、DEF-26）需长会话数据；
   - 无权限角色组合（DEF-02、DEF-10）需新建自定义角色验证。
3. **共性问题**：多个列表页存在「筛选条件被整体覆盖」「无请求竞态保护」「末页删除不回收」三类模式化缺陷，建议抽象统一的列表 Hook 收口。
4. **测试工具提醒**：`agent-browser` 的 `fill` 命令可能触发中间提交态，实测交互请以显式 `click` 为准。

---

> 本报告为只读测试产物，未修改任何业务代码。测试过程中新增的数据已全部自行清理。
