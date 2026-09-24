# 规格点回收台账 · PFP-STOP-RECEIPT-SELFREF-20260924

- [x] SPE-1 | 回执快照==顶部标题、且上一条回执快照不同（本轮落过新交接棒）时，判为已核销、新会开工不阻塞 | 证据：tests/test-stop-receipt-selfref.py 时序1（修复前红、修复后绿）
- [x] SPE-2 | 负向：该轮未落新交接棒（快照==顶部标题==上一条回执快照）时仍判未核销、照旧柔性阻塞 | 证据：tests/test-stop-receipt-selfref.py 时序2 断言 `【柔性阻塞】` 仍在
- [x] SPE-3 | 真机复验：zhengjie-hrm wt-p4 的 20260924-070803-stop.json 由「阻塞」转为「已核销」，且只读不改业务仓库 | 证据：只读 import 复跑 → 参照回执 20260924-070803-stop.json，`render_stop_reports` 无输出、逐条 5/5 已核销；wt-p4 `flow/budget` 仍 5 条
- [x] SPE-4 | 人工验收（ATDD）通过后归档 | 证据：tests/accept-pending-cards.py 13 条断言全绿（用户 2026-09-24 指令：用 tdd 和 atdd 验证并回收）；flow-gc.py --task-archive 已归档到 flow/history/tasks/，回执见 flow/gc/receipts/
