ticket_id: PFP-RELAY-IDENTITY-20260925
schema: v2
objective: 接力提示词必须自带交接身份（源 thread/源卡/源交接棒）、任务说明与下一步，且卡在 [-] 时也能解析
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：flow/budget/*-stop.json（thread_id）、flow/进展.md 顶部交接棒（标题/现状/还剩/下一步）、flow/specs/<ticket>.md（未回收规格点）、flow/tasks/<ticket>.md
  输出：接力提示词含四段——交接来源（源 thread id + 源 ticket + 交接棒标题）、任务说明（一句话是什么+现状）、
        下一步（第一件事 + 验收标准 + 未回收规格点数）、只读取清单；ticket 解析覆盖 plan.md 的 [ ] 与 [-] 两区
  边界：不改软阻塞/核销语义；不改四分区看板契约；业务仓库只读
write_whitelist: scripts/flow-budget.py,tests/test-relay-identity.py,CHANGELOG.md,VERSION
depends_on: 无
red_test: tests/test-relay-identity.py
verify_command: python3 tests/test-relay-identity.py
acceptance: Given 一次正常收工交接，When 生成接力提示词，Then 含源 thread id/源 ticket/交接棒标题/一句话任务说明/下一步；Given 卡已转入 [-] 待验收，Then 仍能解析出该 ticket
evidence: tests/run-all.sh 22 项 Exit 0
next_agent: 人工验收
next_action: 人工验收后移入 flow/history/tasks/
spec_ledger: flow/specs/PFP-RELAY-IDENTITY-20260925.md
