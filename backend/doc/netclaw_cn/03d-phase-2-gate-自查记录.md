# Phase 2 Gate 自查记录

## 1. 文档目的

本文件用于记录 Phase 2 在正式验收前的研发侧 gate 自查结果，逐条对照验收标准，明确证据、残余风险和建议结论。

## 2. 自查范围

本次自查覆盖以下交付物：

- `03-phase-2-变更治理主链.md`
- `03a-phase-2-完成包与自查记录.md`
- `03b-phase-2-低风险变更模板清单.md`
- `03c-phase-2-审计留痕字段规范.md`
- `backend/apps/api/agent_views.py`
- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`
- `backend/apps/workflow_center/models.py`

## 3. 验收标准逐条自查

| 验收标准 | 自查结果 | 证据 | 说明 |
|---|---|---|---|
| 无审批不能执行 | 通过 | `test_change_view_blocks_execution_without_approval` | 未提供 `approval_status=approved` 时直接拒绝执行 |
| 无 baseline 不能执行 | 通过 | `test_change_view_blocks_execution_without_baseline` | 未提供 `baseline_ref` 时直接拒绝执行 |
| 执行后必须 verify | 通过 | `agent_views.change_run` | `change_run` 强制生成 verify 结果合同并写入 execution |
| verify 失败必须 rollback 或挂起待人工确认 | 通过 | `test_change_view_rolls_back_when_verify_fails` | 当前最小实现已覆盖 verify 失败 + rollback 执行 |
| 审计留痕完整记录工单、执行人、触发源、状态、结论 | 通过 | `03c`；`agent_views.change_run` | `order_code`、`commit_user`、`origin`、`remote_ip`、`state`、`task_result` 已纳入 |
| 变更合同对 agent 可解释，不暴露内部混乱状态 | 通过 | `agent_views.change_run` | 输出已统一为 `task_id`、`execution_id`、`status`、`summary`、`artifacts`、`audit_ref`、`rollback_ref` |

## 4. 关键场景复核

### 4.1 门禁场景

已覆盖：

- 无审批执行拦截
- 无 baseline 执行拦截

### 4.2 正常变更

已覆盖：

- verify 成功时返回 `SUCCEEDED`
- 数据库级 execution ledger 回放可查询 `baseline_ref`、`verify_passed`

### 4.3 失败变更

已覆盖：

- verify 失败时触发 rollback
- 数据库级 execution ledger 回放可查询 `ROLLED_BACK` 状态与 `rollback_ref`

## 5. 当前残余风险

- 当前仅 `sec_policy_low_risk` 已纳入真实模板验证，地址对象、服务对象、DNAT 仍停留在模板清单阶段。
- 当前数据库级回放测试仍提示 `automation`、`django_celery_beat`、`django_celery_results`、`network_analysis`、`workflow_center` 存在未生成 migration 的模型变更警告。
- 当前 `analysis` 与变更主链之间尚未建立更强的联动验证闭环。

## 6. 阻塞性判断

- 当前未发现会导致 Phase 2 立即 `REJECT` 的显式阻塞项。
- 当前存在残余风险，但均已限界，适合作为 `PASS_WITH_WAIVER` 候选而不是 `PASS`。

## 7. 统一验收模板映射

- `phase`：`Phase 2`
- `decision`：`待验收负责人确定`
- `summary`：`Phase 2 已完成 change_run 最小合同、execution 状态机、baseline/verify/rollback 引用与数据库级回放证据`
- `blocking_issues`：`无明确阻塞项`
- `waivers`：
  - `建议登记：低风险模板覆盖面仍有限`
  - `建议登记：若干 app 存在未生成 migration 警告`
- `required_followups`：
  - 扩展低风险模板到地址对象、服务对象、DNAT
  - 清理相关 app 的 migration 警告
  - 在下一阶段复核 execution ledger 是否仍存在跨模块分散问题

## 8. 研发侧建议结论

- 建议状态：`IN_REVIEW`
- 建议 gate 结论：`PASS_WITH_WAIVER`

建议原因：

- 核心变更门禁和回滚闭环已经具备
- 数据库级回放证据已经形成
- 但模板覆盖面和 migration 警告仍不足以支持直接 `PASS`

## 9. 证据引用

- `backend/apps/api/agent_views.py`
- `backend/apps/api/tests_agent_v1.py`
- `backend/apps/api/tests_agent_v1_integration.py`
- `backend/apps/workflow_center/models.py`
- `03a-phase-2-完成包与自查记录.md`
- `03b-phase-2-低风险变更模板清单.md`
- `03c-phase-2-审计留痕字段规范.md`
- `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1 -v 2`
- `backend/venv/bin/python backend/manage.py test apps.api.tests_agent_v1_integration -v 2 --keepdb`
