# 团队开发规范

## 目标

本文件用于约束 BasePlatform 仓库的默认协作方式，适用于人工开发者和代码代理，并与参考项目 `/Users/lijiamin/PycharmProjects/workflow-test/backend/AGENT.md` 保持一致的协作口径。

核心目标：

- 变更尽量小、可 review、可回滚。
- 任务状态透明，过程可追踪。
- 提交记录可读、可追溯。
- 代码、文档、验证结果保持一致。
- 规范贴合当前 Django 项目实际，而不是停留在通用模板。

## 项目结构与模块说明

仓库以后端 Django 项目为中心，核心目录如下：

- `backend/`：主后端工程目录。
- `backend/apps/`：业务应用目录，如 `asset`、`automation`、`config_center`、`system`、`users` 等。
- `backend/utils/`：公共工具与共享能力。
- `backend/netaxe/`：Django 配置、路由、ASGI/WSGI 等框架级入口。
- `backend/templates/`、`backend/static/`、`backend/media/`：模板、静态资源和运行期文件。
- `config/`：配置文件目录，`config.json` 存放本地配置，`defaults.json` 存放默认配置。
- `dockerfiles/`、`nginx/`、`docker-compose.yml`：部署与容器化资源。
- `doc/`：项目文档、阶段性总结和排障资料。

## 基本原则

- 优先做小步快跑，不做无边界的大改。
- 优先修根因，不优先堆补丁。
- 一个 commit 只做一类逻辑变更。
- 行为变更、重构清理、文档更新，能拆就拆。
- 涉及生产链路时，优先考虑幂等、日志、回滚和观测性。
- 接口、任务调度、采集流程、配置下发行为变化后，文档必须同步更新。
- 除非需求明确允许，否则默认保持向后兼容。

## 环境、启动与常用命令

Django 相关命令默认在 `backend/` 目录执行：

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
python manage.py test
python manage.py test apps.asset
coverage run --source='.' manage.py test && coverage report
celery -A netaxe worker -l info -Q default
daphne -b 0.0.0.0 -p 8001 netaxe.asgi:application
```

容器化开发常用命令：

```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
```

## 标准工作流

每个任务按以下顺序推进：

1. 明确范围、目标输出和影响模块。
2. 阅读现有实现与受影响文件，确认上下游依赖。
3. 记录假设、风险、配置前置条件和回滚方式。
4. 先做最小正确改动，再考虑抽象和清理。
5. 进行可执行的验证，并保留验证结论。
6. 自查 diff，确认没有混入无关修改。
7. 编写清晰的 commit message。
8. 更新任务进度、文档和后续事项。

## 分支与变更策略

- 一个分支只聚焦一个主题。
- 一个 commit 只表达一个完整意图。
- 不要把无关改动混入当前任务。
- 已共享历史默认不重写，除非团队明确同意。
- 高风险操作前必须先确认影响范围、数据影响和回滚方式。

建议分支命名：

- `feature/<topic>`
- `fix/<topic>`
- `refactor/<topic>`
- `docs/<topic>`
- `chore/<topic>`

## Git 暂存与引用完整性约束

这部分是仓库级强制约束，用于避免出现“代码还在引用新模块，但新模块文件被 stash / checkout / restore 收走”的半完成状态。

本仓库已发生过一次真实问题：

- `backend/apps/dcs_control/views.py` 中新增了对 `serializers.py`、`policy_audit.py` 等文件的引用。
- 后续执行 `git stash` 时，未跟踪的新文件被收进 stash，而部分已跟踪改动仍留在工作区。
- 结果变成“引用存在、被引用文件不存在”，最终触发 `ModuleNotFoundError`。

根因总结：

- 新增 import 的已跟踪文件，与新增的未跟踪配套文件没有作为一个原子变更集一起管理。
- 使用 `git stash -u` 后，没有立即检查工作区是否真的干净。
- 在 stash 出现异常或部分成功后，没有先修复工作区一致性，就继续后续操作。

强制性约束：

- 只要某个已跟踪文件新增了对新模块、新迁移、新文档或新路由文件的引用，这些文件必须视为一个“配套变更集”，不能拆开 stash、restore、checkout、提交或回滚。
- 严禁让已跟踪代码处于“引用未跟踪文件”的中间状态超过当前操作步骤；如果必须中断，优先临时提交或单独分支保存，不优先依赖 stash。
- 执行 `git stash`、`git checkout`、`git restore`、`git cherry-pick`、手工恢复文件后，必须立即执行 `git status --short`，确认不存在“已跟踪引用文件仍在，但配套新文件消失”的情况。
- 对包含 Python import 链、Django `urls.py`、`views.py`、`serializers.py`、`models.py` 变更的任务，stash 或恢复后必须做一次导入级冒烟验证。
- 如果 `git stash` 或索引操作返回异常、锁文件错误、部分成功结果，必须先处理一致性问题，再继续开发，不允许带病继续推进。

推荐操作顺序：

1. 先用 `git status --short` 识别本次变更中的“配套变更集”。
2. 如果存在“已跟踪文件 + 新增未跟踪文件”的组合，优先：
   - 临时提交到本地分支，或
   - 明确使用 `git stash -u`
3. stash 后立刻再次执行 `git status --short`。
4. 对涉及 Django 导入链的改动，至少执行以下之一：
   - `python -m py_compile <files>`
   - `python manage.py shell -c "import apps.xxx.views"`
   - `python manage.py test <targeted_tests>`
5. 若发现工作区进入半状态，第一优先级是恢复缺失文件或回到一致状态，不先写新代码。

## 编码与实现约定

- 遵循 PEP 8，使用 4 空格缩进，单行长度控制在 120 字符内。
- 命名采用 `snake_case`、`PascalCase`、`UPPER_SNAKE_CASE`。
- 优先使用 Django ORM、DRF 的 `ViewSet` + `Serializer` 模式。
- 模型字段优先补充 `verbose_name`、`related_name`。
- 鼓励添加类型标注，但不为了形式牺牲可读性。
- `autopep8` 已在依赖中提供，提交前应格式化改动文件。
- 函数职责保持单一，命名要能直接表达业务意图。
- 注释只解释意图、约束和边界条件，不解释显而易见的语句。
- 能复用现有抽象时不要重复造轮子，新 helper 优先放在最贴近调用逻辑的位置。

针对本仓库的高风险改动，必须额外检查：

- 设备采集、配置下发、自动化任务是否幂等。
- Celery 异步任务失败、重试、超时后的状态是否一致。
- 配置中心、资产管理、设备 API 是否存在兼容性问题。
- 日志是否足够定位问题，同时不会泄露账号、密码、Token 等敏感信息。
- 数据迁移、定时任务、缓存键、文件生成逻辑是否可回滚或可清理。

## 测试与验证规范

项目使用 Django `TestCase` 和 DRF API 测试，测试通常位于 `backend/apps/*/tests.py`。

命名约定：

- 测试类名建议使用 `<模块或对象>TestCase`，如 `DeviceAPITestCase`。
- 测试方法统一使用 `test_<behavior>`。

推荐验证顺序：

1. 定向单测或集成测试。
2. 静态检查、格式化或类型检查。
3. 语法编译检查。
4. 定向人工验证。
5. 安全的 dry-run、回放或联调验证。

最低要求：

- 提交前至少运行 `python manage.py test`，迭代时可先定向运行改动 app 的测试。
- 新增或修改功能的覆盖率目标不低于 70%。
- 如果更强的验证没有执行，必须说明尝试了什么、为什么没跑成、剩余风险是什么。

## Commit 规范

统一使用：

`<type>: <summary>`

推荐类型：

- `feat`：新增功能或新行为。
- `fix`：缺陷修复、回归修复。
- `refactor`：重构，不期望改变外部行为。
- `docs`：仅文档修改。
- `test`：仅测试修改。
- `chore`：配置、依赖、脚手架、日常维护。
- `perf`：性能优化。

提交要求：

- 标题尽量控制在 72 个字符内。
- `summary` 默认使用简洁中文，直接描述结果。
- 使用祈使句，不使用 `update`、`change`、`fix issue` 这类空泛表述。
- 如有必要，在空行后补充 body，说明改了什么、为什么改、风险点或发布说明。

推荐示例：

- `feat: 增加设备插件管理器基础能力`
- `fix: 修复设备采集任务重复入队问题`
- `refactor: 拆分配置中心校验逻辑`
- `docs: 补充设备接口开发接入说明`
- `test: 为拓扑接口补充回归测试`

## Pull Request 与合并要求

PR 或合并说明至少应包含：

- 业务背景和本次改动目标。
- 影响的 app、配置文件、数据库或任务链路。
- 是否包含 migration、配置项变更、定时任务变更。
- 验证方式和结果。
- 风险点、回滚方式和发布后观察点。
- 涉及管理后台或前端页面变化时，附截图或录屏。

## Review 检查清单

提交前至少自查以下事项：

- 范围是否只覆盖当前任务。
- 是否修改了无关文件。
- 是否覆盖正常路径、异常路径和边界条件。
- 用户可见错误信息是否和真实失败原因一致。
- 文档内容是否和实现一致。
- 是否存在明显回归风险。

如果改动触达以下链路，还要额外检查：

- 设备采集、自动化任务、配置下发是否会重复执行。
- Redis、数据库、文件状态是否一致。
- Celery 任务重试、并发执行、失败回滚是否符合预期。
- API 请求和响应字段是否保持兼容。
- migration 是否安全，历史数据是否需要补偿脚本。
- 外部系统凭据、SSH 信息、第三方接口密钥是否被错误打印或提交。

## 文档与配置规范

以下变化必须同步文档：

- API 行为变化。
- 采集、自动化、调度、配置下发流程变化。
- 运维脚本、部署方式、配置项变化。
- 开发流程、排障方式变化。

文档至少应包含：

- 目的。
- 使用方式。
- 输入输出。
- 已知限制。

配置与安全要求：

- 不要提交真实凭据或环境专属密钥到 `config/config.json`。
- 功能性提交中不要混入 `backend/logs/`、`backend/media/`、`backend/venv/` 等运行时产物。
- 新增配置项时，需要同时更新默认值、示例值和使用说明。

## 开发任务进度规范

每个任务必须有明确状态，统一使用：

- `TODO`
- `IN_PROGRESS`
- `BLOCKED`
- `IN_REVIEW`
- `DONE`

推荐任务表模板：

| ID | 任务 | 负责人 | 状态 | 验证 | 备注 |
|---|---|---|---|---|---|
| T-001 | 示例任务 | name | TODO | pending | 范围、依赖或风险 |

状态更新要求：

- 状态变化后立即更新，不要事后补。
- 没做验证前不能标记为 `DONE`。
- 若被阻塞，必须写清阻塞点和下一步动作。
- 若只完成一部分，拆出剩余任务，不允许模糊收尾。
- 若任务较多，可在 `doc/` 中维护详细进度文档，但 `AGENTS.md` 中至少保留当前阶段关键任务摘要。

## 完成定义

只有满足以下条件，任务才算真正完成：

- 功能或修复已完成。
- 验证已执行，或已明确说明无法执行的原因。
- 必要文档已更新。
- diff 已自查，没有混入无关改动。
- commit message 符合规范。
- 后续事项已记录。

## 发布与回滚要求

涉及生产影响的改动，在合并前应补充发布说明：

- 影响模块。
- 外部行为变化。
- 配置或依赖要求。
- 回滚方式。
- 发布后观察点。

推荐记录模板：

- 变更：`<summary>`
- 风险：`<low|medium|high>`
- 回滚：`<revert commit / 回退配置 / 回滚部署 / 回退 migration>`
- 发布后验证：`<日志、任务状态、数据库、第三方回调、设备执行结果等>`

## 当前任务进度列表

| ID | 任务 | 负责人 | 状态 | 验证 | 备注 |
|---|---|---|---|---|---|
| T-20260313-01 | 对齐 BasePlatform 与 workflow-test 仓库级开发规范 | team | DONE | self-review | `AGENTS.md` 已补齐团队开发规范、commit 规范与任务进度模板 |
| T-20260316-01 | 推进 device_api 父方案主导配置与 NETCONF 处理器补齐 | codex | DONE | `backend/venv/bin/python backend/manage.py test apps.device_api.tests.DeviceApiP5RolloutCommandTests -v 2` | P5-06 已收口并完成验收结论留痕，当前为 `PASS_WITH_WAIVER`（见 `p5_acceptance_decision.json`） |
| T-20260316-02 | 建立四任务总体验收门禁、验收模板与总清单 | codex | DONE | self-review | 四任务验收方式与当前状态已合并到 `doc/10-当前任务与验收总览.md` |
| T-20260316-03 | 清理四任务统一测试底座阻塞并推进总体验收 | codex | IN_PROGRESS | pending | 当前统一阻塞和验收关注点统一记录在 `doc/10-当前任务与验收总览.md` |
| T-20260320-02 | 发起 NetClaw-CN 总体验收并回写结论 | codex | DONE | 文档总览复核 + 阶段结论汇总 | 总体验收结论已回写到 `backend/doc/netclaw_cn/README.md`，当前为 `PASS` |
| T-20260320-03 | 制定活跃豁免整改计划 | codex | DONE | self-review | 活跃豁免整改计划已用于推进复核并完成收口，相关中间文档已归档移除 |
| T-20260320-04 | 完成活跃豁免复核并收口 NetClaw-CN 文档 | codex | DONE | `backend/venv/bin/python backend/manage.py test apps.network_analysis.tests apps.network_analysis.tests_integration -v 2 --keepdb` + `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 apps.api.tests_agent_v1_integration -v 2 --keepdb` + `backend/venv/bin/python backend/manage.py makemigrations --check` | 4 个活跃豁免已关闭，NetClaw-CN 整体验收结论已提升为 `PASS`，文档已收口 |
| T-20260323-01 | 完成 Hillstone 防火墙 CLI 数据采集适配并切换配置解析到 TextFSM | codex | DONE | `python3 -m py_compile backend/apps/device_api/fields_mapping.py backend/apps/device_api/__init__.py backend/apps/device_api/models_api.py backend/apps/device_api/indexes.py backend/apps/device_api/platform_profiles.py backend/apps/device_api/processors/hillstone.py backend/apps/device_api/tools/hillstone.py backend/apps/device_api/tasks.py backend/apps/device_api/tests.py` + `backend/venv/bin/python backend/manage.py test apps.device_api.tests.DeviceApiHillstoneGoldenSampleTests -v 2` | 已补齐 Hillstone `show version/arp/mac/interface/service predefined/zone/show configuration/show policy hit-count top 50` 采集适配，`security_policy/dnat/snat` 改为 TextFSM 解析，并兼容多种 NAT 写法 |
| T-20260323-02 | 摸排 CE16800-X8 Huawei YunShan MAC NETCONF 路径并评估批量刷新前置条件 | codex | DONE | 只读 NETCONF capability/get-schema/get + 只读 SSH `display mac-address` | 已在一台 `CE16800-X8` YunShan 样机上确认 schema 候选路径为 `/mac:mac/mac:vlan-dynamic-macs/mac:vlan-dynamic-mac`，但设备当前 CLI MAC 表为空，NETCONF `get` 返回空 `data`；暂不批量刷新画像与自动绑定，详见 `backend/doc/huawei_yunshan_ce16800_x8_mac_netconf_probe_20260323.md` |
| T-20260323-03 | 对齐 Huawei YunShan 与 Huawei CE 的 NETCONF 采集能力并补齐设备信息回填 | codex | DONE | `python3 -m py_compile backend/apps/device_api/processors/huawei.py backend/apps/device_api/platform_profiles.py backend/apps/device_api/models_api.py backend/apps/device_api/tests.py` + `cd backend && venv/bin/python manage.py test apps.device_api.tests.DeviceApiHuaweiIdentityTests apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_route_table_netconf_processor_extracts_yunshan_unicast_routes apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_version_netconf_processor_maps_yunshan_system_info apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_board_status_netconf_processor_maps_yunshan_board_inventory apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_lldp_netconf_processor_maps_yunshan_neighbors apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_aggre_port_netconf_processor_maps_yunshan_trunk_members apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_netconf_capability_processor_maps_schema_features apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_bgp_neighbors_netconf_processor_maps_yunshan_peers_config apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_bgp_summary_netconf_processor_maps_yunshan_peer_totals -v 2 --keepdb --noinput` | 已基于两台 YunShan 实机补齐 `device_identity/netconf_capability/board_status/lldp/aggre_port/route_table/bgp_neighbors/bgp_summary` 适配，`version:netconf` 已可回填 `asset.NetworkDevice`，当前结论与 XML 样本见 `backend/doc/huawei_yunshan_netconf_alignment_20260323.md` |
| T-20260323-04 | 审计 Huawei 交换机画像绑定并加固 YunShan 判型，支撑全网 plan_collect_device_main 全量采集前置校验 | codex | DONE | `python3 -m py_compile backend/apps/device_api/platform_profiles.py backend/apps/device_api/processors/huawei.py backend/apps/device_api/management/commands/audit_huawei_switch_profile_bindings.py backend/apps/device_api/tests.py` + `cd backend && venv/bin/python manage.py test apps.device_api.tests.DeviceApiBridgeCommandTests.test_audit_huawei_switch_profile_bindings_command_reports_fixable_and_manual_conflicts apps.device_api.tests.DeviceApiHuaweiIdentityTests apps.device_api.tests.DeviceApiHealthExtensionTests.test_match_profile_prefers_huawei_yunshan_for_ce16800_x8 apps.device_api.tests.DeviceApiHealthExtensionTests.test_match_profile_prefers_huawei_yunshan_for_ce16808_asset_model apps.device_api.tests.DeviceApiHealthExtensionTests.test_match_profile_prefers_huawei_yunshan_when_identity_platform_name_matches apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_version_netconf_processor_maps_yunshan_system_info apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_bgp_neighbors_netconf_processor_maps_yunshan_peers_config apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_bgp_summary_netconf_processor_maps_yunshan_peer_totals -v 2 --keepdb --noinput` + `cd backend && venv/bin/python manage.py test apps.device_api.tests.DeviceApiAutoBindingCutoverTests.test_auto_bind_devices_reuses_cached_default_plan_per_profile apps.device_api.tests.DeviceApiBridgeCommandTests.test_audit_huawei_switch_profile_bindings_command_reports_fixable_and_manual_conflicts -v 2 --keepdb --noinput` + `cd backend && venv/bin/python manage.py audit_huawei_switch_profile_bindings --sample-limit 20` + `cd backend && venv/bin/python manage.py audit_huawei_switch_profile_bindings --fix-auto-bind --sample-limit 20 --output doc/huawei_switch_profile_binding_audit_after_fix_20260323.json` + `cd backend && venv/bin/python manage.py audit_huawei_switch_profile_bindings --sample-limit 20 --output doc/huawei_switch_profile_binding_audit_postcheck_20260323.json` | 已新增 Huawei 交换机绑定审计命令，YunShan 判型支持 `CE16808` 及 `identity facts` 打分；批量自动修正已完成，Huawei 交换机由 `375/954` 台正确提升到 `942/954` 台正确，两台 YunShan 样机均已收敛到 `Huawei-YunShan`，剩余 `12` 台为手工/legacy 冲突设备，不再自动改写，详见 `backend/doc/huawei_yunshan_netconf_alignment_20260323.md` |
| T-20260323-05 | 清理 Huawei 交换机空手工绑定冲突并修正批次调度对空 manual binding 的误判 | codex | DONE | `python3 -m py_compile backend/apps/device_api/tasks.py backend/apps/device_api/management/commands/audit_huawei_switch_profile_bindings.py backend/apps/device_api/tests.py` + `cd backend && venv/bin/python manage.py test apps.device_api.tests.DeviceApiBridgeCommandTests.test_audit_huawei_switch_profile_bindings_command_can_retire_empty_manual_conflicts apps.device_api.tests.DeviceApiTaskTests.test_plan_collect_device_main_prefers_executable_binding_over_empty_manual_binding apps.device_api.tests.DeviceApiBridgeCommandTests.test_audit_huawei_switch_profile_bindings_command_reports_fixable_and_manual_conflicts apps.device_api.tests.DeviceApiTaskTests.test_plan_collect_device_main_deduplicates_devices_and_skips_empty_sub_plans -v 2 --keepdb --noinput` + `cd backend && venv/bin/python manage.py audit_huawei_switch_profile_bindings --fix-empty-manual-conflicts --sample-limit 20 --output doc/huawei_switch_profile_binding_audit_after_manual_cleanup_20260323.json` + `cd backend && venv/bin/python manage.py audit_huawei_switch_profile_bindings --sample-limit 20 --output doc/huawei_switch_profile_binding_audit_post_manual_cleanup_20260323.json` | 已新增仅退役空 manual/legacy active binding 的安全清理开关，清理 `10` 台残留空手工绑定后，Huawei 交换机正确绑定提升到 `952/954`；`plan_collect_device_main` 去重已优先保留有 `sub_plans` 的 binding，避免空 manual binding 导致设备被误跳过，剩余真实冲突设备收敛到 `2` 台 |
| T-20260323-06 | 修复 Huawei 画像评分顺序误判并完成全网交换机绑定收口 | codex | DONE | `python3 -m py_compile backend/apps/device_api/platform_profiles.py backend/apps/device_api/tests.py` + `cd backend && venv/bin/python manage.py test apps.device_api.tests.DeviceApiHealthExtensionTests.test_match_profile_prefers_capability_profile_when_probe_succeeds apps.device_api.tests.DeviceApiHealthExtensionTests.test_match_profile_preserves_huawei_s_series_match_over_netconf_capability_bias apps.device_api.tests.DeviceApiHealthExtensionTests.test_match_profile_prefers_huawei_yunshan_for_ce16800_x8 apps.device_api.tests.DeviceApiHealthExtensionTests.test_match_profile_prefers_huawei_yunshan_for_ce16808_asset_model apps.device_api.tests.DeviceApiHealthExtensionTests.test_match_profile_prefers_huawei_yunshan_when_identity_platform_name_matches apps.device_api.tests.DeviceApiHealthExtensionTests.test_match_profile_for_huawei_ce98xx_device -v 2 --keepdb --noinput` + `cd backend && venv/bin/python manage.py audit_huawei_switch_profile_bindings --fix-empty-manual-conflicts --sample-limit 20 --output doc/huawei_switch_profile_binding_audit_after_match_fix_cleanup_20260323.json` + `cd backend && venv/bin/python manage.py audit_huawei_switch_profile_bindings --fix-auto-bind --sample-limit 20 --output doc/huawei_switch_profile_binding_audit_after_ce98_rootfix_apply_20260323.json` + `cd backend && venv/bin/python manage.py audit_huawei_switch_profile_bindings --sample-limit 20 --output doc/huawei_switch_profile_binding_audit_post_ce98_rootfix_apply_serial_20260323.json` | 已修复 `match_profile_for_device()` 中 capability 分数压过型号系列匹配的根因，并批量修正 `406` 台残留误判设备；最终 Huawei 交换机 `954/954` 台画像与方案绑定正确，`profile_mismatch/plan_mismatch/manual_binding_conflict` 全部归零 |
| T-20260323-07 | 补齐 Huawei-USG 防火墙 CLI+NETCONF 采集适配到 device_api | codex | DONE | `python3 -m py_compile backend/apps/device_api/fields_mapping.py backend/apps/device_api/__init__.py backend/apps/device_api/indexes.py backend/apps/device_api/models_api.py backend/apps/device_api/platform_profiles.py backend/apps/device_api/processors/huawei.py backend/apps/device_api/tests.py` + `cd backend && venv/bin/python manage.py test apps.device_api.tests.DeviceApiHealthExtensionTests.test_apply_profile_defaults_populates_huawei_usg_netconf_templates apps.device_api.tests.DeviceApiHealthExtensionTests.test_apply_profile_defaults_sets_huawei_usg_cli_commands apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_hrp_state_netconf_processor_maps_usg_state apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_security_policy_netconf_processor_maps_usg_rules apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_snat_netconf_processor_maps_usg_nat_policy apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_dnat_netconf_processor_maps_usg_nat_server apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_address_set_netconf_processor_maps_usg_objects apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_nat_address_netconf_processor_maps_usg_address_group apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_service_set_netconf_processor_maps_usg_objects apps.device_api.tests.DeviceApiProtocolExtensionTests.test_huawei_slb_and_vrrp_netconf_processors_map_usg_payloads -v 2 --keepdb --noinput` | `Huawei-USG` 已切到 CLI+NETCONF 双采集模型：CLI 默认启用 `display arp all`/`display mac-address`/`display lldp neighbor`，NETCONF 默认启用 `get_address_set/get_hrp_state/get_interface_list/get_nat_address/get_nat_policy/get_nat_server/get_sec_policy/get_service_set/get_slb_info/get_system_info/get_trunk_lacp/get_vrrp_info` 对应子方案；并补齐 `hrp_state/address_set/nat_address/service_set/slb_info/vrrp_info/security_policy/dnat/snat` 的字段映射、Mongo 落库和 Huawei 处理器注册 |
| T-20260320-01 | 启动 Phase 4 MCP 与 Skill 产品化基线 | codex | DONE | `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 -v 2` | Phase 4 已以 `PASS_WITH_WAIVER` 正式回写，豁免项见 `backend/doc/netclaw_cn/07-风险台账与豁免记录.md` |
| T-20260319-06 | 启动 Phase 3 拓扑意图与漂移最小实现 | codex | DONE | `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 apps.network_analysis.tests -v 2` | Phase 3 已以 `PASS_WITH_WAIVER` 正式回写，豁免项见 `backend/doc/netclaw_cn/07-风险台账与豁免记录.md` |
| T-20260319-05 | 启动 Phase 2 变更治理主链最小实现 | codex | DONE | `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 -v 2` + `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb` | Phase 2 已复验通过，当前为 `PASS_WITH_WAIVER`，豁免项见 `backend/doc/netclaw_cn/07-风险台账与豁免记录.md` |
| T-20260319-03 | 整改 Phase 1 认证链阻塞项 | codex | DONE | `python3 backend/manage.py test apps.api.tests_agent_v1 -v 2` | `agent/v1` 已补齐认证与权限控制，匿名拒绝 / IAM 身份通过测试已覆盖，等待复验关闭 `RID-P1-001` |
| T-20260319-04 | 推进 Phase 1 数据库级回放证据补齐 | codex | DONE | `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb` | 已补齐数据库级回放证据，并通过 `config_center` migration 与测试序列化配置修复测试底座阻塞 |
| T-20260319-02 | 推进 NetClaw-CN Phase 1 统一只读主链开发 | codex | DONE | `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 -v 2` + `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb` | Phase 1 已复验通过，当前为 `PASS_WITH_WAIVER`，豁免项见 `backend/doc/netclaw_cn/07-风险台账与豁免记录.md` |
| T-20260319-01 | 启动 NetClaw-CN Phase 0 架构定版与遗留切割 | codex | DONE | 文档逐条对照 + 仓库现状复核 | Phase 0 已正式验收通过，结论已回写到 `backend/doc/netclaw_cn/` |
| T-20260324-01 | 完成锐捷交换机 CLI 采集适配并统一入库字段 | codex | DONE | `python3 -m py_compile backend/apps/device_api/platform_profiles.py backend/apps/device_api/tools/ruijie.py backend/apps/device_api/processors/ruijie.py backend/apps/device_api/tests.py` + `backend/venv/bin/python backend/manage.py test apps.device_api.tests.DeviceApiP3GoldenSampleTests apps.device_api.tests.DeviceApiRuijieIdentityTests apps.device_api.tests.DeviceApiHealthExtensionTests.test_apply_profile_defaults_populates_ruijie_cli_commands apps.device_api.tests.DeviceApiProtocolExtensionTests.test_ruijie_lldp_detail_template_parses_cli_rows apps.device_api.tests.DeviceApiProtocolExtensionTests.test_ruijie_lldp_template_registered_in_index -v 1 --keepdb` | 已补齐 `show ip interface brief/show interfaces status/show ip arp/show mac/show aggregatePort summary/show version/show switch virtual/show member` 及 LLDP CLI 解析，ARP/MAC/LLDP/INTERFACE/LAGG 已统一字段入库；未做现网联调，LLDP 命令按 `show lldp neighbors detail` 假设实现 |
| T-20260324-02 | 审计并加固 device_api 定时采集主链并补齐 Mongo 执行日志 | codex | DONE | `python3 -m py_compile backend/apps/device_api/__init__.py backend/apps/device_api/indexes.py backend/apps/device_api/tasks.py backend/apps/device_api/tests.py` + `cd backend && venv/bin/python manage.py test apps.device_api.tests.DeviceApiTaskTests apps.device_api.tests.DeviceApiMongoIndexTests.test_ensure_device_api_mongo_indexes_creates_declared_indexes apps.device_api.tests.DeviceApiMongoIndexTests.test_bootstrap_device_api_mongo_indexes_swallows_errors -v 1 --keepdb` | 已完成 `plan_collect_device_main` / `plan_collect_device` code review 与主链加固，补齐批次/设备/子方案级 `DeviceApiExecutionLog` 留痕，增强 dispatch failure、空处理结果覆盖度和本地调度 `TestDeviceCollection` 明细落库，支撑生产环境按 Mongo 快速定位异常设备与覆盖缺口 |
