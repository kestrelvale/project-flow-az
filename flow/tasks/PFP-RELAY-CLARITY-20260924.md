ticket_id: PFP-RELAY-CLARITY-20260924
schema: v2
objective: 交接以「说清楚」为第一优先：撤掉交接棒体积拦截，并让接力提示词自包含工作根与具体 ticket 路径
mode: plan
method: SDD,TDD,ATDD,BDD
scope: |
  输入：flow/进展.md 顶部交接棒（任意长度）；flow-budget.py 写熔断回执/--print-relay 生成的接力提示词
  输出：① 交接棒不再因体积被拦（防复述仍由最长连续照抄>=400字符/比例>=60% 的检测承担）；
        ② 接力提示词含工作根绝对路径 + flow/tasks/<真实ticket>.md + flow/specs/<真实ticket>.md，
           并声明「cwd 不是工作根时先 cd」，不再给 <ticket> 占位符与纯相对路径
  边界：只做提示词与体积判据，不改软阻塞/核销语义；不碰业务仓库；ticket 识别不出来时保留占位符并在提示词里说明
write_whitelist: scripts/flow-budget.py,scripts/flow-boot.py,scripts/flow-gc.py,tests/test-relay-clarity.py,references/会话预算与接力SOP.md,references/任务状态机与按需加载SOP.md,CHANGELOG.md,VERSION
depends_on: 无
red_test: tests/test-relay-clarity.py
verify_command: python3 tests/test-relay-clarity.py
acceptance: Given 交接棒超过旧上限，When 开工，Then 不再报体积问题；Given 生成接力提示词，Then 含工作根绝对路径与具体 ticket 的 tasks/specs 路径
evidence: tests/run-all.sh 19 项 Exit 0
next_agent: 人工验收
next_action: 人工验收后移入 flow/history/tasks/
spec_ledger: flow/specs/PFP-RELAY-CLARITY-20260924.md
