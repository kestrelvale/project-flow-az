ticket_id: PFP-ORPHAN-RECEIPT-20260923
schema: v2
objective: 提供显式作废「所属会话已消失的孤儿熔断回执」的命令，解开永久柔性阻塞
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：flow/budget/*-stop.json（含 thread_id 与 handoff_head）
  输出：flow-boot.py --void-stale-receipt 输出作废回执 + 写 flow/gc/receipts/ 留痕；之后开工不再阻塞
  边界：不自动判定孤儿（必须显式指定回执或 --older-than），不删除历史交接棒
write_whitelist: scripts/flow-boot.py,tests/test-orphan-receipt.py,CHANGELOG.md,VERSION
depends_on: 无
red_test: tests/test-orphan-receipt.py
verify_command: python3 tests/test-orphan-receipt.py
acceptance: Given 一个 owner 会话已消失的孤儿回执，When 显式作废，Then 开工不再报「未交接」且留痕可审计
evidence: tests/run-all.sh 17 项 Exit 0
next_agent: 人工验收
next_action: 人工验收后移入 flow/history/tasks/
spec_ledger: flow/specs/PFP-ORPHAN-RECEIPT-20260923.md
