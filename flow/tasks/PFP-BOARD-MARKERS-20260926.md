ticket_id: PFP-BOARD-MARKERS-20260926
schema: v2
objective: 严格化 board_visible：锚定 flow-deliver 的分区契约，挡掉空承诺/讨论/引用规则的假阳性
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：上一轮对外回复正文（已剥模型草稿）、flow-deliver.py 的 BOARD_SECTIONS 契约
  输出：只有当回复里出现全部四个分区标题行（行首起）才判「已贴看板」；
        空承诺（「我确保会输出…」）、讨论看板 bug、引用规则原文、任意二级标题 一律判「未贴」
  边界：分区标题从 flow-deliver 派生（单一真相源）；派生失败时返回 False（宁可漏报不误报）；
        不改四分区渲染契约；不碰业务系统
write_whitelist: scripts/flow-budget.py,tests/test-report-visibility.py,CHANGELOG.md,VERSION
depends_on: 无
red_test: tests/test-report-visibility.py
verify_command: python3 tests/test-report-visibility.py
acceptance: Given 回复含四个分区标题行，Then 判为已贴；Given 只说「我会输出任务状态看板」或讨论看板 bug 或引用规则原文，Then 判为未贴
evidence: tests/test-report-visibility.py 绿（6 段假阳性全挡 + 正向不误报）；篡改①退回 in 判断→红、篡改②分区键切早→红、篡改③去 emoji 锚点→红；还原 sha256 一致；bash tests/run-all.sh 23 项 Exit 0（v4.15.21）
next_agent: 人工验收
next_action: 人工验收后移入 flow/history/tasks/
spec_ledger: flow/specs/PFP-BOARD-MARKERS-20260926.md
