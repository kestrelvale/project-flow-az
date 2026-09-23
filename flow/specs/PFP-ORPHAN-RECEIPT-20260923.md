# 规格点回收台账 · PFP-ORPHAN-RECEIPT-20260923

- [x] SPE-1 | 命令能列出候选孤儿回执（owner 会话在 sessions 里已无 rollout） | 证据：tests/test-orphan-receipt.py 列候选断言 + 真机 `flow-boot.py . --void-stale-receipt` 候选 0 条（活会话回执不入列）
- [x] SPE-2 | 显式作废后写 flow/gc/receipts/ 留痕，且开工不再阻塞 | 证据：tests/test-orphan-receipt.py 断言 flow/gc/receipts/<时间>-void-*.json 的 operation=receipt_void/original.handoff_head，且作废后 boot 不再报「上一轮预算 STOP 未交接」
- [x] SPE-3 | 不得自动作废：无显式参数时行为完全不变（负向断言） | 证据：tests/test-orphan-receipt.py 负向三断言（只列不改 / 点名不存在回执 rc!=0 / 点名活会话回执 rc!=0 且不写留痕）
