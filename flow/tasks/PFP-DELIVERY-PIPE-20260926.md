ticket_id: PFP-DELIVERY-PIPE-20260926
schema: v2
objective: 机检不得把「模型草稿」当「对外回复」：看板可见性判定必须基于真正的对外正文
mode: execute
method: SDD,TDD,ATDD,BDD
scope: |
  输入：thread 的 rollout jsonl（response_item 的 role=="assistant" 正文、event_msg 的 task_complete.last_agent_message）
  输出：① last_visible_reply 优先返回 assistant 正文，回退路径也剥离 <analysis>/<summary>/<thinking>/<tool_command>；
        ② 剥完为空时判「不可判定」，打印「上轮回复无法判定」并提示以磁盘看板/回执为准，不点名漏贴；
        ③ flow-boot 把「不可判定」与「缺失任务看板」分开，后者才进路由阻塞
  边界：不改四分区看板契约；不改接力提示词语义；不新增依赖；业务仓库只读
write_whitelist: scripts/flow-budget.py,scripts/flow-boot.py,tests/test-report-visibility.py,CHANGELOG.md,VERSION
depends_on: 无
red_test: tests/test-report-visibility.py
verify_command: python3 tests/test-report-visibility.py
acceptance: Given 上一轮 last_agent_message 只含 <analysis>/<summary> 草稿，Then 判「无法判定」且不判漏贴；Given 草稿与真看板同处一条消息，Then 看穿草稿判为已贴；Given 只有 event_msg 老会话，Then 回退路径同样剥草稿
evidence: tests/test-report-visibility.py 绿（含草稿-only/混合/回退三场景）；篡改 strip_model_scratch 或回退剥离 → 变红；bash tests/run-all.sh 23 项 Exit 0（v4.15.20）
next_agent: 人工验收
next_action: 人工验收后移入 flow/history/tasks/
spec_ledger: flow/specs/PFP-DELIVERY-PIPE-20260926.md
