# Plan 模式交接 SOP

## 什么时候交给 Codex Plan Mode

满足任一条件时先进入 Plan Mode：

- 涉及多个模块、多个仓库或超过一个写入边界；
- 用户要求先规划、评审方案或列出取舍；
- 需要架构调整、数据迁移、权限/支付/发布等高风险变更；
- 需求存在重大歧义，直接编码会造成不可逆返工。

单文件小修、已有明确输入输出和测试命令的 Bug 修复，直接走 Execute Mode，不强制进入 Plan Mode。

## 交接前主控动作

1. 主控 Agent 在 `flow/tasks/<ticket>.md` 创建任务卡，填写 `ticket_id`、`objective`、`scope`、`write_whitelist`、`acceptance`。
2. 任务卡 `mode` 设为 `plan`，`next_agent` 明确写 `Codex Plan Mode`。
3. 执行门禁：

   ```bash
   python3 ~/.codex/skills/project-flow-az/scripts/flow-gate.py flow/tasks/<ticket>.md --phase plan
   ```

4. 在 `flow/进展.md` 顶部写交接棒，只交付指针和剩余决策，不把全量历史塞进新会话。

## Plan Mode 的职责

Plan Mode 只做只读分析和计划，不修改业务代码。它必须返回：

- 方案边界和不做什么；
- SDD 原子任务、依赖和写入白名单；
- TDD/ATDD/BDD 的验证策略；
- 风险、回滚点和需要人工确认的选项；
- Execute Mode 的第一个具体动作。

Plan Mode 结束后，任务卡改为 `mode: execute`，补齐 `verify_command`，再执行：

```bash
python3 ~/.codex/skills/project-flow-az/scripts/flow-gate.py flow/tasks/<ticket>.md --phase execute
```

## 交接给下一个 Codex 会话

只有任务卡门禁通过、交接棒已落盘、当前代码没有未说明的半成品时，才交给下一个 Codex 会话。新会话首动仍运行 `flow-boot.py`，然后只读取：

- 当前任务卡；
- `flow/进展.md` 顶部一条；
- 当前任务需要的规范文件。

## 禁止事项

- 不把 Plan Mode 当成后台执行器；
- 不在 Plan Mode 直接改业务代码；
- 不用“已规划”代替测试和交付；
- 本流程中的 `plant` 指 Plan（计划模式），不是额外的图示工具。
