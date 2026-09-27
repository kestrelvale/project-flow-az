# 规格点回收台账 · PFP-DELIVERY-PIPE-20260926

- [x] SPE-1 | last_visible_reply 优先读 response_item 的 assistant 正文 | 证据：tests/test-report-visibility.py 混合场景（草稿+真看板 → 判为已贴）
- [x] SPE-2 | 剥离 <analysis>/<summary>/<thinking>/<tool_command> 含未闭合块 | 证据：strip_model_scratch 单测 7 例全绿；篡改恒等化 → 测试变红
- [x] SPE-3 | 剥完为空判「不可判定」，不点名漏贴 | 证据：flow-budget 打印「上轮回复无法判定」；flow-boot 分开入路由阻塞；tests 草稿-only 场景
- [x] SPE-4 | 回退路径（仅 event_msg 老会话）同样剥草稿 | 证据：tests 回退场景；篡改回退剥离 → 变红「回退路径没剥草稿」
