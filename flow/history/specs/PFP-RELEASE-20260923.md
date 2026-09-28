# 规格点回收台账 · PFP-RELEASE-20260923

- [x] SPE-1 | 十四个版本已推送到 origin/main（HEAD b19f005） | 证据：git log origin/main -1
- [x] SPE-2 | 全量回归 Exit 0 | 证据：tests/run-all.sh 与 tests/accept-pending-cards.py（19 项 PASS）
- [x] SPE-3 | 人工验收通过后归档到 flow/history/tasks/ | 证据：用户 2026-09-24 指令「用 tdd 和 atdd 测试验证并回收这些待验收的任务」；tests/accept-pending-cards.py 全绿，随后 flow-gc.py --task-archive 归档
