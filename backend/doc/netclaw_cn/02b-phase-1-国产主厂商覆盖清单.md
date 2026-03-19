# Phase 1 国产主厂商覆盖清单

## 1. 文档目的

本文件用于补齐 Phase 1 验收所需的“国产主厂商巡检基线覆盖状态”正式证据，覆盖 Huawei、H3C、Ruijie、Hillstone、ZTE、Maipu、Centec 七类目标厂商。

证据来源：

- `backend/apps/device_api/doc/p1_coverage_report.json`
- `backend/apps/device_api/platform_profiles.py`
- `backend/apps/device_api/doc/当前能力.md`

统计时间基线：

- `2026-03-17` 覆盖审计快照

## 2. 总体覆盖结论

按 `p1_coverage_report.json` 的审计结果，七个目标厂商当前覆盖情况如下：

| 厂商 | 当前设备总数 | ready | blocked | 代表画像 | 默认方案 | 当前结论 |
|---|---:|---:|---:|---|---|---|
| Huawei | 959 | 959 | 0 | `Huawei-CE` / `Huawei-S` / `Huawei-USG` | `default-huawei-ce-switch` / `default-huawei-s-switch` / `default-huawei-usg-firewall` | 已覆盖，当前样本全部 ready |
| H3C | 2805 | 2804 | 1 | `H3C-modern-netconf` / `H3C-legacy-cli` / `H3C-firewall-cli` / `H3C-router-cli` | `default-h3c-modern-switch` / `default-h3c-legacy-switch` / `default-h3c-firewall` / `default-h3c-router` | 已覆盖，存在 1 个阻塞样本 |
| Ruijie | 12 | 12 | 0 | `Ruijie-switch` | `default-ruijie-switch` | 已覆盖，当前样本全部 ready |
| Hillstone | 94 | 94 | 0 | `Hillstone-firewall` | `default-hillstone-firewall` | 已覆盖，当前样本全部 ready |
| ZTE | 0 | 0 | 0 | `ZTE-switch` | 运行样本为 0 | 画像已定义，当前审计样本为 0 |
| Maipu | 2 | 2 | 0 | `Maipu-switch` | `default-maipu-switch` | 已覆盖，当前样本全部 ready |
| Centec | 0 | 0 | 0 | `Centec-switch` | 运行样本为 0 | 画像已定义，当前审计样本为 0 |

## 3. 阻塞原因清单

当前七厂商范围内仅发现 1 类阻塞原因：

| 厂商 | 阻塞码 | 数量 | 说明 |
|---|---|---:|---|
| H3C | `missing_ssh_account` | 1 | 设备已匹配画像与默认方案，但缺少本地 Netmiko 采集所需 SSH 账号绑定 |

本轮未发现以下阻塞码在七厂商范围内出现：

- `profile_not_matched`
- `missing_default_plan`
- `missing_binding`
- `missing_netconf_account`
- `missing_execute_node`

## 4. 画像定义与默认方案说明

### 4.1 Huawei

当前已定义画像：

- `Huawei-S`
- `Huawei-CE`
- `Huawei-router-cli`
- `Huawei-USG`
- `Huawei-YunShan`

当前有运行样本落入的画像：

- `Huawei-CE`
- `Huawei-S`
- `Huawei-USG`

### 4.2 H3C

当前已定义画像：

- `H3C-legacy-cli`
- `H3C-modern-netconf`
- `H3C-router-cli`
- `H3C-firewall-cli`

当前有运行样本落入的画像：

- `H3C-legacy-cli`
- `H3C-modern-netconf`
- `H3C-firewall-cli`
- `H3C-router-cli`

### 4.3 Ruijie

当前已定义画像：

- `Ruijie-switch`

### 4.4 Hillstone

当前已定义画像：

- `Hillstone-firewall`

### 4.5 ZTE

当前已定义画像：

- `ZTE-switch`

当前审计样本为 0，说明“画像定义存在”，但“线上样本覆盖”尚无本轮证据。

### 4.6 Maipu

当前已定义画像：

- `Maipu-switch`

### 4.7 Centec

当前已定义画像：

- `Centec-switch`

当前审计样本为 0，说明“画像定义存在”，但“线上样本覆盖”尚无本轮证据。

## 5. 对 Phase 1 验收的意义

本文件解决了 `RID-P1-002` 中“国产主厂商巡检基线覆盖清单缺失”的一部分问题：

- 已补齐七厂商的默认绑定与阻塞原因清单
- 已明确哪些厂商是“已有线上样本覆盖”，哪些是“画像已定义但当前样本为 0”

仍未解决的部分：

- 单设备巡检成功的真实回放证据
- 安全审计结果独立查询与回放证据

## 6. 证据引用

- `backend/apps/device_api/doc/p1_coverage_report.json`
- `backend/apps/device_api/platform_profiles.py`
- `backend/apps/device_api/doc/当前能力.md`
