ticket_id: PFP-RELAY-MULTITASK-20260924
schema: v2
objective: 接力提示词在多任务并行/多工作区下指名正确任务，不再猜错卡或给出死路径
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：--intent（可能显式点名某编号）、flow/plan.md 活跃区条目（条目文字可能引用别的卡编号）
  输出：意图中显式点名的编号拥有最高优先级——活跃区有它就用它；活跃区没有它就照实说「不在活跃区」，
        绝不被子串包含该编号的**其它**卡兜底
  边界：不改显式 --ticket 最高优先级；不改文字匹配作为无显式点名时的回退；不改软阻塞/核销语义
write_whitelist: scripts/flow-budget.py,tests/test-relay-multi-task.py,CHANGELOG.md,VERSION
depends_on: 无
red_test: tests/test-relay-multi-task.py
verify_command: python3 tests/test-relay-multi-task.py
acceptance: Given 意图点名 B 卡、B 不在活跃区，而活跃区 A 卡条目文字含 B 编号，When 解析 ticket，Then 返回 B（照实说不存在）而非 A；Given 意图未点名任何编号，Then 才回退文字匹配
evidence: tests/test-relay-multi-task.py 打回断言③ + tests/run-all.sh 22 项 Exit 0（v4.15.19）
next_agent: 人工验收
next_action: 已修复，「点名 B 却返回 A」，再把显式点名块上移到匹配循环之前
spec_ledger: flow/specs/PFP-RELAY-MULTITASK-20260924.md
