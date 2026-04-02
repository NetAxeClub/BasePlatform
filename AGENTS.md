# BasePlatform 仓库协作说明

适用对象：人工开发者与代码代理。

目标：

- 小步提交，便于 review、回滚和定位问题。
- 变更范围清晰，过程可追踪，验证有结论。
- 规范以当前 Django 项目实际结构为准。

## 项目目录树

仓库主树：

```text
.
├── AGENTS.md
├── CHANGELOG.md
├── LICENSE
├── README.md
├── backend
│   ├── __init__.py
│   ├── apps
│   ├── bus
│   ├── calls
│   ├── confload
│   ├── database
│   ├── driver
│   ├── init.sh
│   ├── manage.py
│   ├── manager
│   ├── models
│   ├── netaxe
│   ├── plugins
│   ├── requirements.txt
│   ├── rpc
│   ├── scripts
│   ├── service_mesh
│   ├── start.sh
│   ├── static
│   ├── supervisord_prd.conf
│   ├── templates
│   ├── utils
│   ├── uwsgi.ini
│   └── worker.py
├── build.sh
├── config
│   ├── config.json
│   ├── defaults.json
│   ├── log-config.yml
│   └── structured_drift_policy.example.json
├── doc
│   ├── 01-项目概述.md
│   ├── 05-API接口.md
│   ├── 07-部署指南.md
│   ├── 08-开发规范.md
│   ├── 09-架构边界与集成说明.md
│   ├── 10-当前任务与验收总览.md
│   └── README.md
├── docker-compose.yml
├── dockerfiles
│   ├── backend_dockerfile
│   ├── backend_update_dockerfile
│   ├── inner_dockerfile
│   ├── nginx_dockerfile
│   └── web_dockerfile
├── nginx
│   ├── backend_nginx.conf
│   └── nginx.conf
├── plugins
│   └── drivers
└── resource
    ├── asset.jpg
    ├── git-diff.jpg
    ├── login.jpg
    ├── monitor.md
    └── 架构图.jpg
```

`backend/apps`：

```text
backend/apps
├── __init__.py
├── api
├── asset
├── automation
├── config_center
├── dcs_control
├── device_api
├── event
├── int_utilization
├── network_analysis
├── route_backend
├── system
├── topology
├── users
└── workflow_center
```

## 关键目录

- `backend/`：Django 主工程目录，默认在此执行 `manage.py` 命令。
- `backend/apps/`：核心业务 app，重点关注 `device_api`、`api`、`asset`、`config_center`、`network_analysis`。
- `backend/netaxe/`：Django 配置、路由、ASGI/WSGI、Celery 入口。
- `backend/utils/`：公共工具与连接能力。
- `config/`：本地配置、默认配置、日志配置样例。
- `doc/`：项目说明、API、部署、架构边界、验收总览。
- `dockerfiles/`、`nginx/`、`docker-compose.yml`：容器化与部署资源。

## 常用命令

默认在 `backend/` 执行：

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
python manage.py test
python manage.py test apps.device_api
coverage run --source='.' manage.py test && coverage report
celery -A netaxe worker -l info -Q default
daphne -b 0.0.0.0 -p 8001 netaxe.asgi:application
```

容器：

```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
```
## 1. 规范

### 1.1 基本原则
1. 修bug时主动检查相关代码一起修
2. 编辑后运行类型检查和lint验证
3. 回复简洁直接 不要解释性废话
4. 大改动先输出计划再执行，主agent负责拆解任务和测试验收，执行使用subagent
5. 不确定的主动说 不要编造
6. 新功能必须有对应的测试
7. 一次提交只做一件事:一个提交只解决一个明确问题，避免把功能、重构、格式化、配置调整混在一起
8. 优先复用已有抽象:公共逻辑优先收敛到 `backend/utils/` 等共享位置，不重复实现
9. 异步链路禁止阻塞: Celery等异步链路中，禁止继续扩散同步阻塞 I/O
10. 只要涉及到告警链路的改动，必须最后走一次告警链路的回归测试确保质量


### 1.3 安全与配置约束

- 禁止提交真实密钥、密码、Token、数据库连接串和内网敏感地址。
- `config/config.test.json` 仅允许保留脱敏示例值。
- 本地实验脚本、临时排障脚本、导出数据脚本默认不进入正式提交。
- 新增外部服务调用时，必须具备超时、异常日志和失败降级处理。

### 1.4 测试与验证要求

- Python 相关命令必须使用仓库本地虚拟环境，统一使用 `./venv/bin/python`、`./venv/bin/pip` 等路径执行。
- 禁止使用全局 `python`、`python3`、`pip`、`pip3` 直接运行本项目脚本、测试、安装或检查命令。
- 路由契约变化：补 `tests/router_contracts_suite.py` 或等价测试。
- 通用工具变化：补 `tests/route_utils_suite.py` 或等价测试。
- 模型默认值、序列化行为变化：补 `tests/model_defaults_suite.py`。
- 配置初始化或日志初始化变化：补 `tests/confload_suite.py`。
- 至少运行与本次修改直接相关的测试；涉及共享逻辑时，优先运行聚合测试入口 `tests.test_all`。
## Git 与工作区强约束

本仓库严禁出现“已跟踪代码引用了新文件，但新文件被 stash / restore / checkout 收走”的半完成状态。

- 新增 import、路由、迁移、文档引用时，相关文件必须作为同一个“配套变更集”一起管理。
- 不要把“已跟踪文件修改”和“新增未跟踪配套文件”拆开 stash、restore、提交或回滚。
- 执行 `git stash`、`git restore`、`git checkout`、`git cherry-pick` 后，必须立刻执行 `git status --short`。
- 涉及 `views.py`、`serializers.py`、`models.py`、`urls.py`、导入链时，恢复后至少做一次导入级冒烟验证。
- 若 stash 或索引操作出现异常、锁文件、部分成功，先恢复工作区一致性，再继续开发。

推荐最小检查：

```bash
git status --short
python -m py_compile <files>
python manage.py shell -c "import apps.xxx.views"
python manage.py test <targeted_tests>
```

## 编码与验证要求

- 遵循 PEP 8，4 空格缩进，单行不超过 120 字符。
- 优先使用 Django ORM、DRF `ViewSet` + `Serializer` 模式。
- 命名清晰，函数职责单一，注释只解释意图和边界。
- 优先复用现有抽象；新增 helper 放在最贴近调用处。
- 提交前至少运行 `python manage.py test`；迭代阶段可先跑定向测试。
- 新增或修改功能的覆盖率目标不低于 70%。
- 若无法完成更强验证，必须记录已尝试内容、失败原因和剩余风险。

高风险改动额外关注：

- 设备采集、自动化任务、配置下发是否幂等。
- Celery 失败、重试、超时后的状态是否一致。
- API 字段、配置中心、资产管理、设备 API 是否保持兼容。
- 日志是否足以排障且不泄露敏感信息。
- migration、缓存键、文件生成逻辑是否可回滚或清理。

## 文档、配置、提交

- 不提交真实凭据到 `config/config.json`。
- 功能提交不要混入 `backend/logs/`、`backend/media/`、`backend/venv/` 等运行产物。
- 新增配置项时，同步更新默认值、示例值和使用说明。
- 行为变化涉及 API、采集、调度、配置下发、部署时，必须更新 `doc/`。

Commit 格式：

```text
<type>: <summary>
```

推荐类型：`feat`、`fix`、`refactor`、`docs`、`test`、`chore`、`perf`

示例：

- `feat: 增加设备插件管理器基础能力`
- `fix: 修复设备采集任务重复入队问题`
- `docs: 补充设备接口开发接入说明`

PR / 合并说明至少包含：

- 背景与目标
- 影响范围
- 是否含 migration / 配置变更 / 定时任务变更
- 验证方式与结果
- 风险、回滚方式、发布后观察点

## 任务状态与当前摘要

状态统一使用：

- `TODO`
- `IN_PROGRESS`
- `BLOCKED`
- `IN_REVIEW`
- `DONE`

当前阶段仅保留关键摘要，详细历史与验收记录见 `doc/10-当前任务与验收总览.md`。

| ID | 任务 | 负责人 | 状态 | 验证 | 备注 |
|---|---|---|---|---|---|
| T-20260316-03 | 清理四任务统一测试底座阻塞并推进总体验收 | codex | IN_PROGRESS | pending | 当前统一阻塞与验收关注点记录在 `doc/10-当前任务与验收总览.md` |
| T-20260320-02~04 | NetClaw-CN 总体验收与活跃豁免收口 | codex | DONE | 文档复核 + 测试记录 | 当前整体结论为 `PASS` |
| T-20260323-01~07 | `device_api` 华为 / Hillstone / Ruijie 采集适配与绑定收口 | codex | DONE | 定向测试 + 文档留痕 | 详细结论见相关 `backend/doc/` 与验收总览 |
| T-20260324-02 | `device_api` 定时采集主链加固与 Mongo 执行日志补齐 | codex | DONE | 定向测试 | 已完成主链加固与执行留痕补齐 |

