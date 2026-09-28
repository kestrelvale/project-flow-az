ticket_id: PFP-SPEC-ACCUMULATION-20260928
schema: v2
goal: 规格点不再跨任务累积——按卡加载、随卡归档、首屏只显示本卡未回收项
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：用户 2026-09-28 质疑「规格点是不是不应该累积」
  输出：① run_distill_checks 按 ticket 精确加载（定不出则不加载）；
        ② 归档时台账随卡移入 flow/history/specs/；③ 存量孤儿台账清理
  边界：只改 project-flow 框架（scripts/、tests/、flow/），不碰业务系统；不 push 直到用户确认
write_whitelist: scripts/flow-boot.py,scripts/flow-gc.py,tests/test-spec-scope.py,tests/test-spec-archive.py,VERSION,CHANGELOG.md
depends_on: 无
red_test: tests/test-spec-scope.py
verify_command: python3 tests/test-spec-scope.py && python3 tests/test-spec-archive.py
acceptance: Given 未绑定任务卡，When 开工，Then 首屏不加载任何台账；Given 绑定本卡，Then 只显示该卡规格点；Given 归档任务卡，Then 台账移入 history/specs/ 而非滞留
evidence: tests/test-spec-scope.py 全绿 + tests/test-spec-archive.py 全绿 + tests/run-all.sh 28 项 Exit 0
next_agent: Codex
next_action: 人工验收后归档；随后确认是否 push origin
