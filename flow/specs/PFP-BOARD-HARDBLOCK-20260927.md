# 规格点回收台账 · PFP-BOARD-HARDBLOCK-20260927

- [x] SPE-1 | 漏贴看板必须进入「阻断认领」条件，而不仅是 append 到提示列表 | 证据：scripts/flow-boot.py 独立 board_blocker 接入 claim 条件；tests/test-board-hardblock.py::test_variable_is_not_a_thin_alias 绿
- [x] SPE-2 | 硬阻塞必须给出明确文案 | 证据：同测试 ::test_hardblock_message_present_in_source 断言「【硬阻塞】上轮漏贴看板」存在
- [x] SPE-3 | 「无法判定」（草稿剥空）仍与「确定没贴」分开处理 | 证据：源码仍保留「上轮回复无法判定」分支；复用 4.15.21 的 strip_model_scratch
