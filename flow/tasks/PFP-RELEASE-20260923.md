ticket_id: PFP-RELEASE-20260923
schema: v2
objective: v4.15.0 → v4.15.13 十四个版本已推送远端，等人工验收（不重复开工）
mode: review
method: SDD,TDD,ATDD,BDD
scope: |
  输入：远端 origin/main 的 HEAD 与 CHANGELOG
  输出：人工验收结论（通过则归档）
  边界：不再改实现；有问题另开 [[ ]] 卡
write_whitelist: references/交付说明-v4.15.0-4.15.12.md
depends_on: 无
red_test: tests/run-all.sh
verify_command: bash tests/run-all.sh
acceptance: Given 远端已是 b19f005，When 跑全量回归，Then 16 项 Exit 0 且交付说明可达
evidence: tests/run-all.sh 16 项 Exit 0
next_agent: Codex Review Mode
next_action: 人工验收后移入 flow/history/tasks/
spec_ledger: flow/specs/PFP-RELEASE-20260923.md
