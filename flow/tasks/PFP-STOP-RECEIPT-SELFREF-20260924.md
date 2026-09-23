ticket_id: PFP-STOP-RECEIPT-SELFREF-20260924
schema: v2
objective: 熔断回执快照等于当事会话自己那轮交接棒标题时，接手的新会话不再被永久柔性阻塞
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：flow/budget/*-stop.json（thread_id / handoff_head / stopped_at）+ flow/进展.md 顶部交接棒
  输出：flow-boot.py 在「当事会话已落合规交接棒、但回执快照等于该标题」时判为已核销（开工不阻塞）；
        「这一轮确实没落新交接棒」时仍判未核销（fail-closed 不变）
  边界：只放宽 read_pending_stop 的「已核销」判据，用同目录上一条回执的 handoff_head 作对照；
        不改软阻塞语义、不改交接棒格式、不自动修改任何回执文件
write_whitelist: scripts/flow-boot.py,tests/test-stop-receipt-selfref.py,CHANGELOG.md,VERSION
depends_on: 无
red_test: tests/test-stop-receipt-selfref.py
verify_command: python3 tests/test-stop-receipt-selfref.py
acceptance: Given 当事会话先写交接棒、后写回执（快照==标题），When 新会开工，Then 不报柔性阻塞；Given 该轮未写新交接棒，Then 仍报未交接
evidence: tests/run-all.sh 18 项 Exit 0
next_agent: 人工验收
next_action: 人工验收后移入 flow/history/tasks/
spec_ledger: flow/specs/PFP-STOP-RECEIPT-SELFREF-20260924.md
