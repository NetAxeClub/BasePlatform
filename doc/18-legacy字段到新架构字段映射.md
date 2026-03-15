# legacy 字段到新架构字段映射

更新时间：2026-03-15

## 1. 目的

本文件用于说明 legacy `automation` 数据结构与新架构 `device_api` / `workflow_center` 的字段映射关系。

使用原则：

- legacy 字段只作为导入来源，不作为新架构主字段。
- 新架构统一使用新语义字段名。
- 导入命令允许读取旧表，但导入后的新表只对外暴露新字段。

---

## 2. 工作流主机变量映射

旧表：`automation.AutoVars`

新表：`workflow_center.WorkflowHostVar`

| legacy 字段 | 新字段 | 说明 |
|---|---|---|
| `id` | `legacy_id` | 保留旧主键映射，仅用于追踪 |
| `ans_name` | `name` | 主机展示名 |
| `ans_host` | `host` | 主机地址 |
| `ans_vars` | `variables` | 主机变量 JSON/Text |
| `ans_obj` | `object_name` | 对象名称 |
| `ans_memo` | `description` | 描述信息 |
| `task` | `task` | 任务域，语义保留 |

说明：

- `ans_*` 命名不再对外暴露。
- 新代码、API、前端只允许使用 `name/host/variables/object_name/description`。

---

## 3. 工作流库存映射

旧表：`automation.AutomationInventory`

新表：`workflow_center.WorkflowInventory`

| legacy 字段 | 新字段 | 说明 |
|---|---|---|
| `id` | `legacy_id` | 保留旧主键映射，仅用于追踪 |
| `ans_group_name` | `name` | 库存名称 |
| `ans_group_vars` | `variables` | 库存级变量 |
| `ans_group_memo` | `description` | 库存描述 |
| `ans_group_datetime` | `created_at` | 创建时间 |
| `ans_group_hosts` | `hosts` | 库存成员主机 |
| `task` | `task` | 库存任务类型 |

关系映射：

- legacy M2M：`automation_automationinventory_ans_group_hosts`
- 新关系：`WorkflowInventory.hosts`

说明：

- 新架构统一使用 `hosts`，不再使用 `group_hosts` 或 `ans_group_hosts`。
- 新架构统一使用 `created_at`，不再使用 `ans_group_datetime`。

---

## 4. 工作流执行映射

旧表：`automation.AutoFlow`

新表：`workflow_center.WorkflowExecution`

| legacy 字段 | 新字段 | 说明 |
|---|---|---|
| `id` | `legacy_id` | 保留旧主键映射，仅用于追踪 |
| `task_id` | `task_id` | 任务ID |
| `origin` | `origin` | 来源 |
| `task_result` | `task_result` | 任务结果 |
| `order_code` | `order_code` | 工单号 |
| `device` | `device` | 设备IP |
| `device_id` | `device_id` | 设备ID |
| `commit_user` | `commit_user` | 提交人 |
| `commit_time` | `commit_time` | 提交时间 |
| `task` | `task` | 工作流任务类型 |
| `method` | `method` | 执行方式 |
| `class_method` | `class_method` | 逻辑入口 |
| `remote_ip` | `remote_ip` | 调用来源IP |
| `event_id` | `event` | 仅保留事件ID，不再直接绑定 legacy 外键 |
| `kwargs` | `kwargs` | 参数 |
| `ttp` | `ttp` | 解析结果 |
| `commands` | `commands` | 执行命令 |
| `back_off_commands` | `back_off_commands` | 回退命令 |
| `state` | `state` | 流程状态 |
| `code` | `code` | 状态码 |

说明：

- 新表不直接依赖 legacy `AutoEvent` 外键，只保留 `event` 整型引用。
- 工作流巡检辅助解析通过 `workflow_center.inspection` 完成，不依赖 `automation.inspection`。

---

## 5. 采集规则映射

旧表：`collection_rule` / `collection_match_rule`

新表：`device_api.DeviceCollectionRule` / `device_api.DeviceCollectionMatchRule`

| legacy 字段 | 新字段 | 说明 |
|---|---|---|
| `collection_rule.id` | `legacy_rule_id` | 旧规则ID映射 |
| `collection_match_rule.id` | `legacy_match_rule_id` | 旧匹配项ID映射 |
| `name` | `name` | 规则名 |
| `operation` | `operation` | 运算符 |
| `module` | `module` | 执行模块 |
| `method` | `method` | 协议方式 |
| `execute` | `execute` | 执行内容 |
| `plugin` | `plugin` | 解析插件 |
| `fields` | `fields` | 匹配字段 |
| `operator` | `operator` | 匹配操作符 |
| `value` | `value` | 匹配值 |
| `rule_id` | `rule_id` | 关联到新规则主键 |

说明：

- 新规则是 `device_api` 自己的实体模型，不再 proxy legacy 规则表。
- legacy 规则表可作为导入来源和并跑参考，但不再是主写源。

---

## 6. 导入约束

所有导入命令都必须遵守：

- 允许读取 legacy 物理表
- 只写入新表
- 支持幂等
- 支持 dry-run
- 导入后对外只暴露新字段

当前导入命令：

- `python manage.py import_legacy_workflow_data`
- `python manage.py import_legacy_collection_rules`

操作步骤与执行建议参见：

- [19-legacy数据导入操作说明](./19-legacy数据导入操作说明.md)
