# 规格点回收台账 · PFP-RELAY-CLARITY-20260924

- [x] SPE-1 | 交接棒不再因体积被拦（删掉「省字数」硬判据），防复述仍由照抄检测承担 | 证据：tests/test-relay-clarity.py ①11KB 交接棒无「字节（上限」、漏字段仍报「交接棒缺少字段」；flow-boot.py 删除 MAX_HANDOFF_BYTES；两份 SOP + flow-gc 注释同步
- [x] SPE-2 | 接力提示词自包含：工作根绝对路径 + 具体 ticket 的 tasks/specs 路径 + 「cwd 不是工作根先 cd」 | 证据：tests/test-relay-clarity.py ②断言 `<root>/flow/tasks/W2-P4-CANDIDATE-H5-20260922.md`、`<root>/flow/specs/….md`、工作根提示语，且只读取清单无 `<ticket>` 占位符
- [x] SPE-3 | 负向：ticket 识别不出时保留占位符且提示词仍可执行；软阻塞/核销语义不变 | 证据：tests/test-relay-clarity.py ③无 ticket 标题回退占位符且 rc=0；顺带修 UUID 被误当 ticket（current_ticket 先切 thread= 段）；flow-boot 体积判据只删体积、四字段/thread 校验保留
- [x] SPE-4 | 人工验收（ATDD）通过后归档 | 证据：tests/accept-pending-cards.py 13 条断言全绿（用户 2026-09-24 指令：用 tdd 和 atdd 验证并回收）；flow-gc.py --task-archive 已归档到 flow/history/tasks/，回执见 flow/gc/receipts/
