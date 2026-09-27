ticket_id: PFP-RELAY-IDENTITY-20260925
schema: v2
objective: 接力提示词必须自带交接身份（源 thread/源卡/源交接棒）、任务说明与下一步，且「源交接棒」必须按 ticket 精确定位
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：flow/进展.md（可含多张卡的交接棒，顶部常属于并发会话的另一张卡）、flow/plan.md（活跃区/待验收区）
  输出：接力提示词的「来源交接棒」「任务说明（现状/还剩/卡在哪）」只来自解析出的那张卡的交接棒；
        该卡在进展.md 无交接棒时照实写「交接棒未声明」，绝不贴另一张卡的内容
  边界：不改软阻塞/核销语义；不改四分区看板契约；不改 resolve_ticket 的显式 --ticket 语义；业务仓库只读
write_whitelist: scripts/flow-budget.py,tests/test-relay-multi-task.py,CHANGELOG.md,VERSION
depends_on: PFP-RELAY-MULTITASK-20260924
red_test: tests/test-relay-multi-task.py
verify_command: python3 tests/test-relay-multi-task.py
acceptance: Given 顶部交接棒属于 A 卡、本轮意图指向 B 卡，When 生成接力提示词，Then「来源交接棒」与「现状/还剩/卡在哪」全部来自 B 卡；Given 目标卡在进展.md 无交接棒，Then 明确写未声明而非贴他卡内容
evidence: tests/test-relay-multi-task.py 打回断言①② + tests/run-all.sh 22 项 Exit 0（v4.15.19）
next_agent: 人工验收
next_action: 已修复，「来源交接棒贴 A 卡」，再改 handoff_fields 按 ticket 定位
spec_ledger: flow/specs/PFP-RELAY-IDENTITY-20260925.md
