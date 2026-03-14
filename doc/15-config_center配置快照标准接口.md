# config_center 配置快照标准接口

## 目标

为 NetClaw-CN 提供稳定的配置备份读取接口，统一输出：

- 最新配置快照
- 配置历史时间线
- 配置版本对比

避免上层分别拼接 `ConfigBackup`、`ConfigComplianceResult` 和 Git 接口。

## 1. 最新配置快照

- 路径：`GET /base_platform/config_center/config_backup/latest_snapshot/`

参数：

- `manage_ip`：必填，设备管理 IP
- `config_type`：可选，默认 `running`
- `include_preview`：可选，`true/false`
- `preview_lines`：可选，默认 `50`

返回重点字段：

- `config_backup_id`
- `manage_ip`
- `device_name`
- `vendor`
- `config_type`
- `backup_time`
- `config_status`
- `file_path`
- `git_commit_count`
- `latest_commit`
- `compliance_summary`
- `compliance_results`
- `preview_content`

## 2. 配置历史时间线

- 路径：`GET /base_platform/config_center/config_backup/history_timeline/`

参数：

- `manage_ip`：必填，设备管理 IP
- `config_type`：可选，不传表示全部
- `limit`：可选，默认 `20`

返回重点字段：

- `manage_ip`
- `config_type`
- `count`
- `items`

每个 `item` 包含：

- `config_backup_id`
- `backup_time`
- `config_status`
- `file_path`
- `git_commit_count`
- `latest_commit`
- `compliance_summary`

## 3. 配置版本对比

- 路径：`GET /base_platform/config_center/config_backup/version_compare/`

参数：

- `config_backup_id`：必填
- `from_commit`：可选
- `to_commit`：可选

说明：

- 如果不传 `from_commit` 和 `to_commit`，默认使用该文件最近两次提交进行对比。

返回重点字段：

- `config_backup_id`
- `manage_ip`
- `device_name`
- `vendor`
- `config_type`
- `file_path`
- `from_commit`
- `to_commit`
- `old_content`
- `new_content`
- `old_line_count`
- `new_line_count`
- `added_lines`
- `deleted_lines`

## 当前限制

- 版本对比依赖 `file_path` 对应文件存在 Git 历史提交。
- 当文件历史不足两次提交时，默认对比模式会返回提示，需要后续继续产生备份版本。
