# 规格点回收台账 · PFP-RELAY-MULTITASK-20260924

- [x] SPE-1 | 显式交接身份：--ticket/--work-root 写进回执，提示词不再从交接棒标题猜 ticket | 证据：tests/test-relay-multi-task.py（顶部交接棒是 A 卡、意图指向 B 卡 → 提示词给 B 卡；显式 --ticket 覆盖意图与顶部）；flow-budget.py 新增 --ticket/--work-root
- [x] SPE-2 | 卡不存在/已归档时不给死路径，改为列出 plan.md 活跃区候选 | 证据：tests/test-relay-multi-task.py（已归档卡 → 不出现 flow/tasks/<死卡>.md，改列活跃区候选）；tests/test-relay-clarity.py 同步收紧（未指定 ticket 时不再给占位符死路径）
- [x] SPE-3 | 提示词附并行队列（[ ] 前 N 条）与阻塞项（[!]），并声明分端 worktree 与主仓合并分工 | 证据：tests/test-relay-multi-task.py（队列含 B/C 两张、出现阻塞提示与工作根/分工声明）
- [x] SPE-4 | 破损修复：handoff_prompt 曾调用已被替换的 current_ticket（NameError） | 证据：重写后 tests/run-all.sh 21 项 Exit 0
