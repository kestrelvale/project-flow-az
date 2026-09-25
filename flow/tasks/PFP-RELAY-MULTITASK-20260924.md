ticket_id: PFP-RELAY-MULTITASK-20260924
schema: v2
objective: 接力提示词在多任务并行/多工作区下指名正确任务，不再猜错卡或给出死路径
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：flow/plan.md 活跃区（[ ]/[-]/[!]）；可选显式 --ticket / --work-root；flow/budget/*-stop.json
  输出：接力提示词显式带 work_root + ticket + 活跃队列表；ticket 卡不存在时标注并从活跃区列候选；
        无显式 ticket 时按 --intent 匹配活跃卡，匹配不到就说「未指定」而不是编造
  边界：不改软阻塞/核销语义；不自动跨工作区执行；不读取 history/ 候选
write_whitelist: scripts/flow-budget.py,tests/test-relay-multi-task.py,CHANGELOG.md,VERSION
depends_on: 无
red_test: tests/test-relay-multi-task.py
verify_command: python3 tests/test-relay-multi-task.py
acceptance: Given 顶部交接棒是 A 卡而本轮意图是 B 卡，When 生成接力提示词，Then 指向 B 卡；Given 卡已归档，Then 不给出不存在的卡路径而是列活跃区候选
evidence: tests/run-all.sh 21 项 Exit 0
next_agent: 人工验收
next_action: 人工验收后移入 flow/history/tasks/
spec_ledger: flow/specs/PFP-RELAY-MULTITASK-20260924.md
