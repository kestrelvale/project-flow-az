# 任务卡
#
# 四阶段单向流转：plan(Plan/Goal/SDD) -> execute(TDD) -> review(ATDD) -> handoff(BDD)
# 每进入下一阶段，只改 mode/method 并补齐该阶段必填字段，不要跳阶段。
# 字段值保持单行；如确需换行请用 `key: >` 块标量并保证后续行缩进，解析器会拼回正文。

ticket_id: P0-1
goal: <一句话目标：可观察的结果，不是做法>
mode: plan
method: SDD,TDD,ATDD,BDD
scope: <输入、输出、边界和失败状态>
write_whitelist: <允许修改的文件或目录>
verify_command: <可复现的 Exit 0 验证命令>
acceptance: <Given-When-Then 或可执行验收断言>
evidence: <验证凭证路径，交付前填写>
next_agent: Codex Plan Mode
next_action: <交接给下一模式的第一个动作>

## Plan 阶段产出 (Plan / Goal / SDD)

- 目标与成功判据：
- 方案边界与不做的事：
- SDD 原子任务与 I/O 契约：
- 风险与人工决策门：
- 退出条件：

## Execute 阶段产出 (TDD)

- 失败测试（先红）：
- 实际改动：
- 最小实现：
- 测试结果（Exit 0）：

## Review 阶段产出 (ATDD)

- 可执行验收断言：
- 验收证据路径：

## Handoff 阶段产出 (BDD)

- Given-When-Then：
- 下一步交接：
- 交付物路径：
