# 任务卡
#
# 四阶段单向流转：plan(Plan/Goal/SDD) -> execute(TDD) -> review(ATDD) -> handoff(BDD)
# 每进入下一阶段，只改 mode/method 并补齐该阶段必填字段，不要跳阶段。
# 字段值保持单行；如确需换行请用 `key: >` 块标量并保证后续行缩进，解析器会拼回正文。
# schema: v2 表示走严格产物门禁；老卡无此字段则沿用宽松规则。

ticket_id: P0-1
schema: v2
goal: <一句话目标：可观察的结果，不是做法>
mode: plan
method: SDD,TDD,ATDD,BDD
scope: |
  输入：<触发方式、字段、有效与无效边界>
  输出：<返回值、界面状态、文件或日志变化>
  边界：<不做的事与失败状态>
write_whitelist: <允许修改的文件或目录>
depends_on: <前置任务 ticket_id；多个用逗号分隔，无则留空或写 无>
red_test: <execute 阶段先失败的测试文件路径，先红后绿>
verify_command: <可复现的 Exit 0 验证命令>
acceptance: <Given-When-Then 或可执行验收断言>
evidence: <验证凭证路径，交付前填写>
spec_ledger: flow/specs/P0-1.md
next_agent: Codex Plan Mode
next_action: <交接给下一模式的第一个动作>

## Plan 阶段产出 (Plan / Goal / SDD)

- 问题陈述（用户视角现象）：
- 目标与成功判据：
- 用户故事（As a…, I want…, so that…）：
- 实现决策（模块/接口/schema/契约，不写文件路径）：
- 测试决策（测哪些模块、已有同类先例）：
- 方案边界与不做的事：
- SDD 原子任务与 I/O 契约：
- 规格点台账（把用户需求蒸馏成 SPE-n，逐条回收；进 review 前必须全部回收，
  无规格点的琐碎卡才写 `spec_ledger: none`）：
- 风险与人工决策门：
- 退出条件：

## Execute 阶段产出 (TDD，五拍循环)

每个原子任务独立走完一轮，禁止先写全部测试或先写实现：

1. 写一个失败测试 →
2. 跑它确认按预期失败 →
3. 写最小实现 →
4. 跑全量测试确认全绿 →
5. 提交

- 失败测试（先红）：
- 首次失败输出（证明它真失败过）：
- 实际改动：
- 最小实现：
- 测试结果（Exit 0）：

## Review 阶段产出 (ATDD)

- 可执行验收断言（接口/E2E/脚本）：
- 验收证据路径：
- 无法自动化的部分（可复现命令 + 观测点）：

## Handoff 阶段产出 (BDD)

- Given-When-Then（每条对应一个可观测断言）：
- 下一步交接：
- 交付物路径：

## 按需深挖（结构不够用时读，不常驻）

- 规格不会写 → `~/.codex/skills/to-spec/SKILL.md`
- 拆不细 / 步骤有占位符 → `~/.codex/skills/writing-plans/SKILL.md`
- seam 选错 / 测试写不好 → `~/.codex/skills/test-driven-development/SKILL.md`
- 模块边界不清 → `~/.codex/skills/codebase-design/SKILL.md`
