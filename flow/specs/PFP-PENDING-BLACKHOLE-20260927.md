# 规格点回收台账 · PFP-PENDING-BLACKHOLE-20260927

- [x] SPE-1 | `[ ]` 为空且 `[-]` 堆积超阈值时必须计入路由阻塞 | 证据：scripts/flow-boot.py 新增 pending_blackhole() + MAX_PENDING_CARDS=3；tests/test-pending-blackhole.py::test_blocked_when_no_active_and_pending_pile_up 绿
- [x] SPE-2 | 有 `[ ]` 活跃焦点时不得因 `[-]` 堆积而阻塞（否则永远开不了新活） | 证据：同测试 ::test_not_blocked_when_active_focus_exists 绿
- [x] SPE-3 | `[-]` 未达阈值不阻塞（避免刚交付一张就被拦） | 证据：同测试 ::test_not_blocked_when_pending_below_threshold 绿
- [x] SPE-4 | 阻塞原因必须给出可执行的清账命令 | 证据：原因串含 `flow-gc.py . --apply --task-archive <ticket> --reason user_accepted`
