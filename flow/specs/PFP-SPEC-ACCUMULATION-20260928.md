# 规格点回收台账 · PFP-SPEC-ACCUMULATION-20260928

- [x] SPE-1 | 规格点加载必须按本次要接的卡限定，不得扫全目录 | 证据：flow-boot.py 新增 current_ticket()；run_distill_checks 传 --ticket；tests/test-spec-scope.py::test_spec_scope_only_current_ticket 绿
- [x] SPE-2 | 定不出本轮卡时不加载任何台账（不得兜底扫全量） | 证据：tests/test-spec-scope.py::test_no_ticket_loads_nothing 绿
- [x] SPE-3 | flow-distill 支持 --ticket 限定且确实只读该卡 | 证据：tests/test-spec-scope.py::test_distill_spec_requires_ticket_scoping 绿
- [x] SPE-4 | 任务卡归档时规格点台账必须同步移入 flow/history/specs/ | 证据：flow-gc.py HISTORY_DIRS 加 specs + task_archive 搬台账；tests/test-spec-archive.py::test_ledger_moves_with_card 绿
- [x] SPE-5 | 无台账的卡照常归档，不得因缺台账失败 | 证据：tests/test-spec-archive.py::test_archive_without_ledger_still_works 绿
- [x] SPE-6 | 存量 9 张孤儿台账迁入 history/specs/，flow/specs/ 只留活跃卡 | 证据：ls flow/specs/ 由 12 张降到 3 张；ls flow/history/specs/ 为 9 张
