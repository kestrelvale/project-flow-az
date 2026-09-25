ticket_id: PFP-REPORT-VISIBILITY-20260925
schema: v2
objective: 收工看板与工作汇报必须真实、完整、可见：修渲染矛盾/截断，并对「漏贴看板」加机检点名
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：flow/plan.md 归档分区占位、flow/history/tasks/*.md、flow/decisions.md、rollout 的最后一条 assistant 回复
  输出：①归档分区显示真实归档计数与最近 N 张（不再输出与事实矛盾的「无」）；
        ②决策分区只输出完整条目（多行条目的续行不单独成条）；
        ③新增 board_in_reply 机检，上一轮回复缺看板时在下一轮开工的路由阻塞/回收建议中点名
  边界：不改四分区标题契约与顺序；不改交付回执结构；只读 rollout；不碰业务仓库
write_whitelist: scripts/flow-deliver.py,scripts/flow-budget.py,scripts/flow-boot.py,tests/test-report-visibility.py,CHANGELOG.md,VERSION
depends_on: 无
red_test: tests/test-report-visibility.py
verify_command: python3 tests/test-report-visibility.py
acceptance: Given plan 归档区写着「无」但 history/tasks 有卡，When 收工，Then 看板列出真实计数与最近归档；Given 上一轮回复漏贴看板，Then 下一轮开工点名
evidence: tests/run-all.sh 21 项 Exit 0
next_agent: 人工验收
next_action: 人工验收后移入 flow/history/tasks/
spec_ledger: flow/specs/PFP-REPORT-VISIBILITY-20260925.md
