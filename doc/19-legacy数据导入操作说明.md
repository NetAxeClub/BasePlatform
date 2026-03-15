# legacy 数据导入操作说明

更新时间：2026-03-15

## 1. 目的

本文档用于说明如何将 legacy `automation` 物理表中的历史数据导入到新架构 `workflow_center` / `device_api` 的新表中。

这些导入命令的定位是：

- 冷迁移工具
- 幂等导入工具
- dry-run 预演工具

它们不是运行时主链路的一部分。

---

## 2. 前置约束

执行前必须确认：

1. 新表 migration 已完成
2. 新架构代码已部署到目标环境
3. `automation` 仍可正常兜底
4. 导入阶段不会让新链路反向依赖 legacy 代码

推荐先做：

```bash
cd backend
venv/bin/python manage.py check
```

---

## 3. 导入工作流数据

命令：

```bash
cd backend
venv/bin/python manage.py import_legacy_workflow_data --dry-run
```

正式导入：

```bash
cd backend
venv/bin/python manage.py import_legacy_workflow_data
```

可选参数：

```bash
--limit <N>
--execution-table <table_name>
--hostvar-table <table_name>
--inventory-table <table_name>
--inventory-host-table <table_name>
```

默认表名：

- `auto_work_flow`
- `automation_autovars`
- `automation_automationinventory`
- `automation_automationinventory_ans_group_hosts`

导入目标：

- `workflow_center_execution`
- `workflow_center_host_var`
- `workflow_center_inventory`

导入映射参考：

- [18-legacy字段到新架构字段映射](./18-legacy字段到新架构字段映射.md)

---

## 4. 导入采集规则数据

命令：

```bash
cd backend
venv/bin/python manage.py import_legacy_collection_rules --dry-run
```

正式导入：

```bash
cd backend
venv/bin/python manage.py import_legacy_collection_rules
```

可选参数：

```bash
--limit <N>
--rule-table <table_name>
--match-rule-table <table_name>
```

默认表名：

- `collection_rule`
- `collection_match_rule`

导入目标：

- `device_api_collection_rule`
- `device_api_collection_match_rule`

---

## 5. dry-run 解释

`--dry-run` 会：

- 按真实逻辑读取 legacy 数据
- 执行同样的映射与 upsert 逻辑
- 在事务结束时回滚

因此它适合用来确认：

- 表名是否正确
- 字段映射是否正确
- 数据量是否符合预期
- 导入不会因唯一约束或脏数据直接失败

---

## 6. 导入后核对项

### 6.1 工作流数据

至少核对：

- `workflow_center_execution` 记录数
- `workflow_center_host_var` 记录数
- `workflow_center_inventory` 记录数
- `WorkflowInventory.hosts` 关系是否完整
- 巡检记录中的 `inspection_scope` / `inspection_type` 是否还能正确解析

### 6.2 采集规则数据

至少核对：

- `device_api_collection_rule` 记录数
- `device_api_collection_match_rule` 记录数
- `rule -> match_rule` 关联是否完整
- 新规则接口列表是否能正常返回

---

## 7. 建议执行顺序

推荐按以下顺序做：

1. `check`
2. `import_legacy_collection_rules --dry-run`
3. `import_legacy_workflow_data --dry-run`
4. 核对 dry-run 输出
5. 正式导入规则
6. 正式导入工作流
7. 接口抽样验证
8. 并跑观察

---

## 8. 风险说明

当前导入命令是“从 legacy 表读取并写入新表”的单向导入工具。

这意味着：

- 新表导入成功，不代表已经切流
- 导入后仍需要并跑验证
- 旧 `automation` 仍然保留兜底职责

只有在新链路生产验证通过后，才讨论是否让 `automation` 消失
