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
