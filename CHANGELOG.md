# Changelog

All notable changes to this project will be documented in this file.

## [M11] - 2026-09-09

### Added

- **NL2SQL扩展业务表**
  - 新增对`sys_user`（员工）、`att_record`（考勤）、`sal_payroll`（工资单）表的查询支持
  - 支持跨表JOIN查询，如"技术部上月迟到几次"
  - 更新AI助手工具描述，引导正确使用新表

- **数据范围权限**
  - 角色表新增`data_scope`字段（1仅本人 2本部门 3全部）
  - 新增`get_data_scope()`和`apply_data_scope()`工具函数
  - 考勤、薪资列表接口集成数据范围过滤
  - 角色管理页面增加数据范围选择

- **AI错误类型区分**
  - 新增ErrorType常量（NETWORK/TIMEOUT/AUTH/SERVER/ABORT/UNKNOWN）
  - 根据错误类型显示不同图标和操作建议
  - 网络错误显示WiFi图标，其他错误显示感叹号图标

- **Dashboard扩展**
  - 新增薪资成本趋势图表（柱状图+折线图）
  - 新增各部门薪资分布饼图
  - 新增人力结构分析（性别+年龄双饼图）
  - 新增职位人数TOP8横向柱状图

- **面包屑导航**
  - 新增Breadcrumb组件，基于菜单树动态生成
  - 面包屑显示在内容区顶部

- **Header快捷菜单**
  - 下拉菜单增加"个人资料"和"修改密码"快捷入口
  - 支持用户头像显示

### Fixed

- AIModelOption类型缺少context_window字段
- MemoryDrawer.tsx类型错误
- MessageItem.test.tsx测试用例缺少id字段

### Changed

- NL2SQL可查询表从1张扩展到4张
- 角色Schema增加data_scope字段
- 考勤/薪资服务增加current_user参数

### Migration

- 数据库迁移：`e1f2a3b4c5d6_m11_data_scope.py`
  - sys_role表新增data_scope字段，默认值3（全部）

---

## [M10] - 2026-09-09

### Added

- AI助手用量监控：ai_message增加usage统计列

---

## Previous Versions

See git history for earlier changes.
