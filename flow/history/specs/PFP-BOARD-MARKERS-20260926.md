# 规格点回收台账 · PFP-BOARD-MARKERS-20260926

- [x] SPE-1 | 看板判定锚定带 emoji 的分区标题行，空承诺/讨论/引用规则不再判为已贴 | 证据：tests/test-report-visibility.py 6 段假阳性全挡（空承诺/讨论bug/引用规则/只有大标题/四个无关标题/三个无关+真决策标题）；实测攻击面 7/7 符合预期
- [x] SPE-2 | 分区契约从 flow-deliver 派生（单一真相源），不在 flow-budget 另抄 emoji | 证据：board_section_keys() 经 importlib 读 flow-deliver.BOARD_SECTIONS；测试断言每个键确实出现在 flow-deliver 源码中
- [x] SPE-3 | 反向：真看板（四分区齐全）仍判为已贴，不因严格化误报 | 证据：tests 正向场景（四分区齐全 → 不点名）；实测 7/7
