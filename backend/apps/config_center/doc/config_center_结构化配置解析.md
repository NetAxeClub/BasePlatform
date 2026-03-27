# 配置中心结构化解析说明

## 目的

将配置备份任务产出的非结构化文本，通过统一的 TTP 解析抽象层转换为厂商无关的结构化文档，并落库到 MongoDB，供后续配置检索、差异分析、基线校验和意图建模复用。

## 当前实现

- 统一入口：`apps.config_center.tasks.parse_config_backup_structured`
- 漂移分析入口：`apps.config_center.tasks.analyze_structured_config_drift`
- 统一解析服务：`apps.config_center.config_parse.structured`
- Mongo 集合：`Automation.config_backup_structured`
- 漂移结果集合：`Automation.config_backup_drift`
- 解析引擎：TTP

## 统一文档结构

Mongo 中每条文档固定为以下顶层结构：

- `schema_version`
- `document_type`
- `config_backup_id`
- `device`
- `backup`
- `parser`
- `config`
- `summary`
- `vendor_payload`

其中 `config` 为厂商无关抽象，当前统一字段包括：

- `system`
- `features`
- `routing_instances`
- `vlans`
- `zones`
- `services`
- `ntp_servers`
- `log_hosts`
- `aaa_servers`
- `interfaces`
- `access_lists`
- `snmp`
- `vendor_specific`

## 已支持厂商

- `H3C` / `hp_comware`
- `Huawei` / `HUAWEI`
- `Hillstone`
- `Ruijie`
- `Cisco_ios`

新增厂商时，只需要新增对应 profile 和 TTP 模板，并在 registry 注册，不需要修改 Celery 任务或 Mongo schema。

## 输入输出

输入：

- `ConfigBackup` 记录
- 备份文件路径对应的原始配置文本

输出：

- 一条按 `config_backup_id` 幂等 upsert 的结构化 Mongo 文档

## 查询接口

当前通过 `ConfigBackupViewSet` 暴露六个相关接口：

- `GET /base_platform/config_center/config_backup/latest_structured/`
- `GET /base_platform/config_center/config_backup/structured_timeline/`
- `GET /base_platform/config_center/config_backup/structured_compare/`
- `GET /base_platform/config_center/config_backup/latest_structured_drift/`
- `GET /base_platform/config_center/config_backup/structured_drift_policy/`
- `POST /base_platform/config_center/config_backup/validate_structured_drift_policy/`

另提供数据库策略管理接口：

- `GET/POST /base_platform/config_center/structured_drift_policy_profile/`
- `GET/PUT/PATCH/DELETE /base_platform/config_center/structured_drift_policy_profile/<id>/`
- `POST /base_platform/config_center/structured_drift_policy_profile/<id>/activate/`

### latest_structured

用途：

- 按备份记录 ID 精确获取一条结构化配置快照
- 或按设备 `manage_ip + config_type` 获取最新结构化配置快照

参数：

- `config_backup_id`：可选，优先级最高
- `manage_ip`：当未传 `config_backup_id` 时必填
- `config_type`：可选，默认 `running`

返回重点字段：

- `config_backup_id`
- `manage_ip`
- `device_name`
- `vendor`
- `vendor_family`
- `config_type`
- `backup_time`
- `parser_status`
- `parser_profile`
- `summary`
- `document`

### structured_timeline

用途：

- 获取设备最近若干次结构化解析结果，便于做时间线展示或版本演进观察

参数：

- `manage_ip`：必填
- `config_type`：可选，不传表示全部类型
- `limit`：可选，默认 `20`，最大 `100`

返回重点字段：

- `manage_ip`
- `config_type`
- `count`
- `items`

### structured_compare

用途：

- 按两次结构化快照做对象级差异对比
- 支持显式指定两次备份
- 支持按单个 `config_backup_id` 自动回看上一版
- 支持按 `manage_ip + config_type` 自动对比最近两版

参数：

- `from_config_backup_id`：可选，与 `to_config_backup_id` 成对使用
- `to_config_backup_id`：可选，与 `from_config_backup_id` 成对使用
- `config_backup_id`：可选，传入后自动与同设备同配置类型的上一版对比
- `manage_ip`：可选，当未传上述 ID 参数时必填
- `config_type`：可选，默认 `running`

返回重点字段：

- `from_snapshot`
- `to_snapshot`
- `diff.is_changed`
- `diff.summary`
- `diff.sections`

对比维度：

- `system`
- `features`
- `routing_instances`
- `vlans`
- `zones`
- `services`
- `ntp_servers`
- `log_hosts`
- `aaa_servers`
- `interfaces`
- `access_lists`
- `snmp`
- `vendor_specific`

### latest_structured_drift

用途：

- 获取最近一次已完成的结构化漂移分析结果
- 支持按备份记录精确读取
- 支持按设备与配置类型读取最新漂移结果

参数：

- `config_backup_id`：可选，读取 `to_config_backup_id = config_backup_id` 的漂移结果
- `manage_ip`：当未传 `config_backup_id` 时必填
- `config_type`：可选，默认 `running`

返回重点字段：

- `from_config_backup_id`
- `to_config_backup_id`
- `manage_ip`
- `device_name`
- `vendor`
- `vendor_family`
- `config_type`
- `from_backup_time`
- `to_backup_time`
- `diff_summary`
- `risk_assessment`
- `document`

### structured_drift_policy

用途：

- 查看当前生效的漂移策略
- 确认是否加载了本地覆盖文件
- 查看当前策略校验结果

返回重点字段：

- `policy`
- `validation`
- `source.local_override_loaded`
- `source.local_override_keys`
- `source.active_db_override_loaded`
- `source.active_db_override_keys`

### validate_structured_drift_policy

用途：

- 提交一段策略 JSON 做合并预览
- 在不落盘的前提下验证结构是否合法

请求体：

- 直接传入一个 JSON object，作为对默认策略的覆盖片段

返回重点字段：

- `policy`
- `validation.is_valid`
- `validation.errors`
- `validation.warnings`

## 自动化链路

当前自动化执行顺序为：

1. `backup_device_config`
2. `parse_config_backup_structured`
3. `analyze_structured_config_drift`
4. `config_compliance`
5. `git_push_config`

其中 `analyze_structured_config_drift` 会将当前结构化快照与同设备同配置类型的上一版结构化快照进行对象级对比，并生成：

- 变更 section 摘要
- 风险等级 `risk_level`
- 风险分数 `risk_score`
- 漂移发现列表 `findings`

## 漂移策略与白名单

默认漂移策略文件：

- `backend/apps/config_center/config_parse/structured/policies/default_drift_policy.json`

本地覆盖文件路径：

- `config/structured_drift_policy.json`

示例文件：

- `config/structured_drift_policy.example.json`

数据库持久化策略模型：

- `StructuredDriftPolicy`

激活策略合并顺序：

1. 默认策略
2. 本地覆盖文件
3. 当前激活的数据库策略

当前策略能力包括：

- `section_rules`：定义每个结构化 section 的默认风险等级与标题
- `signal_rules`：定义关键字段变化时的升级规则，例如 `telnet_enabled`、`http_enabled`、`ssh_enabled`
- `whitelist`：定义允许忽略的预期变化

白名单匹配字段当前支持：

- `section`
- `manage_ip`
- `vendor`
- `vendor_family`
- `config_type`
- `path_suffix`
- `key`

效果说明：

- 命中白名单的变化不会进入有效风险结论
- 被抑制的变化仍会保留在 `risk_assessment.suppressed_findings`
- 当前生效策略版本会回写到 `risk_assessment.policy_version`

## 已知限制

- 当前统一 schema 优先覆盖通用对象：系统信息、接口、VRF、VLAN、AAA、日志、NTP、ACL、Zone、Service。
- 厂商私有高级语义暂存于 `vendor_payload` 和 `config.vendor_specific`，避免在第一版抽象中过早耦合业务。
- Hillstone 的服务端口、Zone 模式等少量对象使用 TTP + 正则补充归一化，后续如需扩大覆盖面可继续细化 TTP block。
