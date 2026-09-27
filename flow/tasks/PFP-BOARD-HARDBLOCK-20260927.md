ticket_id: PFP-BOARD-HARDBLOCK-20260927
schema: v2
goal: 漏贴看板从提示升为硬阻塞
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：用户 2026-09-27 指令「帮我完成 A，然后把整个框架修复完整再完成 B」暴露的三处结构性缺陷
  输出：门禁按真实相位判、[-] 堆积阻塞新活、漏贴看板阻断认领；三处各有独立测试
  边界：只改 project-flow 框架（scripts/ 与 tests/），不碰任何业务系统；不 push 直到用户确认
write_whitelist: scripts/flow-boot.py,tests/test-board-hardblock.py
depends_on: 无
red_test: tests/test-board-hardblock.py
verify_command: python3 tests/test-board-hardblock.py
acceptance: Given 卡躺在 flow/plan.md 的 [ ] 区，Then 门禁按 plan 相位判而非卡自报的 mode；Given [ ] 为空且 [-] 超过 3 张，Then 路由阻塞并给出清账命令；Given 上轮回复缺看板，Then 阻断本轮认领
evidence: tests/test-phase-gate-truth.py 全绿 + tests/test-pending-blackhole.py 全绿 + tests/test-board-hardblock.py 全绿 + tests/run-all.sh 26 项 Exit 0
next_agent: Codex
next_action: 人工验收后归档；随后确认是否 push origin
