# 规格点回收台账 · PFP-REPORT-VISIBILITY-20260925

- [x] SPE-1 | 归档分区不再输出与事实矛盾的「无」：显示真实计数 + 最近 N 张归档 | 证据：tests/test-report-visibility.py ①（`已归档 3 张` + `最近：OLD-2`）；tests/test-flow-deliver.py 断言同步更新为新契约
- [x] SPE-2 | 决策分区只输出完整条目，不把多行续行当独立条目、不留半截句 | 证据：tests/test-report-visibility.py ②（多行条目已合并成一条完整决策，无 `` `resolve_ `` 半截续行）；flow-deliver.py 新增 render_decisions()
- [x] SPE-3 | 新增 board_in_reply 机检：上一轮回复漏贴看板时，下一轮开工在路由阻塞/回收建议点名 | 证据：tests/test-report-visibility.py ③（构造漏贴看板的 task_complete.last_agent_message → flow-budget 打印 `上轮回复缺失任务看板`、flow-boot 并入路由阻塞）+ 反向（贴了看板不点名）
- [x] SPE-4 | 顺带修复阻塞态破损：handoff_prompt 调用已被替换的 current_ticket 导致 NameError（任何走提示词的路径直接崩） | 证据：flow-budget.py 重写 handoff_prompt 接入 resolve_ticket/active_queue；tests/test-relay-clarity.py 与 tests/test-relay-multi-task.py 全绿
