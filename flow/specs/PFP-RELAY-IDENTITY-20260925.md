# 规格点回收台账 · PFP-RELAY-IDENTITY-20260925

- [x] SPE-1 | 提示词含交接来源：源会话 thread id + 源任务卡 + 源交接棒标题 | 证据：tests/test-relay-identity.py（断言 SRC_THREAD/TICKET/交接棒三件套）；flow-budget.py 新增 handoff_fields()
- [x] SPE-2 | 提示词含一句话任务说明（这是什么 + 当前状态） | 证据：tests/test-relay-identity.py（断言「任务说明」段含卡 objective「把 X 收口」与现状「已推送」）
- [x] SPE-3 | 提示词含下一步（第一件事 + 验收标准 + 未回收规格点数） | 证据：tests/test-relay-identity.py（断言「下一步」段含 run-all.sh 与「未回收」计数）；pending_specs()/acceptance_of() 支撑
- [x] SPE-4 | 修回归：卡在 [-] 待验收时 ticket 仍可解析（不再恒为「未指定」） | 证据：tests/test-relay-identity.py（夹具卡在待验收区仍解析出 ticket；反向两区皆无时报「未指定」）+ tests/test-relay-multi-task.py（显式点名已归档卡不得被别的卡兜底）
