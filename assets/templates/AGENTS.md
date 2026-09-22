# AGENTS.md · 协作约定 (Claude Code / Codex 共用入口)

> 本文件定义用户个人交互偏好与人机协同底线。具体任务流转以当面指令为最高意图，代码与架构产出落盘实体文件。

<!-- project-flow-cy:start -->
## project-flow 运行时合同

### 1. 开工状态与收工看板

开工时只输出 `project-flow 开工状态`，不得预填尚未发生的验收、归档或决策结果。

```markdown
### project-flow 开工状态

## 🎯 当前聚焦待办 (P0)
- [ ] P0-1 <原子任务> (边界: path/to/file)

## 🚧 路由阻塞
- <无 / 缺少绑定任务卡的焦点>

## 🧹 未纳管遗留
- <无 / 历史债务>
```

任务完成、验证通过并准备提交给用户验收时，必须运行：

```bash
python3 ~/.codex/skills/project-flow-az/scripts/flow-deliver.py flow/tasks/<ticket>.md \
  --changed "<实际改动路径>" --evidence "<Exit 0 证据>" \
  --what "<做了什么>" --why "<为什么这么做>" \
  --understanding "<边界 / 假设>" --outputs "<产出路径>" \
  --problem "<问题 → 怎么解决，没有可省略>" --next-step "<下一步>"
```

并把脚本输出的 `任务状态看板`、`本轮工作汇报` 与 `交付验收卡` 原样粘贴到回复中。禁止只写“flow 状态”摘要，也禁止用任务看板代替工作汇报。

`任务状态看板` 的四个分区标题与顺序是固定契约，由 `flow-deliver.py` 统一生成，不得改写或省略：

```text
## 🎯 当前聚焦待办 (P0)
## ⏳ 待人工验收 (Pending Verification)
## 📦 已完结归档 (Archived in flow/history/)
## 💡 本轮决策记录 (Decisions)
```

空分区写 `- 无`；任务全部归档后看板仍必须完整输出，不得输出空看板或用项目自定义标题替代。

- `[-] 待人工验收`只列本轮真实交付且已有 Exit 0 证据的任务；
- `[✓]`只列已经从活跃区物理归档的任务；
- `决策`只列本轮实际发生的自动决策或人工决策门。

### 2. plan 先落盘

动手前先把用户当轮任务写进 `flow/plan.md`：`[ ]` 待完成（原子任务 + 写入边界 + 验证方式）/ `[-]` 待验收（静默勿动）/ `[✓]` 已完成（当回合剪切至 `flow/history/`）/ `[✕]` 不合格（当轮 P0 修复）。只留活跃任务。

### 3. 每轮硬首动审计

每个执行型回合的第一次工具调用必须运行 `python3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent "<本轮任务摘要>"`；该入口按需热同步、执行审计并输出“接管路由”。必须消费路由结果：

- `活跃 [ ]`：本轮唯一施工焦点；
- `Plan 路由`（项目初期）：先只读执行 Plan / Goal / SDD 规划门，禁止改业务代码；
- `Execute 路由`（实现期）：按 TDD 先写失败测试再最小实现；
- `Review 路由`（验收期）：用 ATDD 可执行断言验收；
- `Handoff 路由`（收尾期）：只读 BDD 交接卡，先转成活跃任务卡再施工；
- `静默任务卡`、`[-]`、`history/`、`trash/`：不得抢占本轮任务；
- `路由阻塞` 或“本轮意图未登记”：先补 `flow/plan.md` 与任务卡，不得直接改业务代码。
- `project-flow 预算 [WARN]`：停止扩展读取范围，只保留当前任务必要文件，并准备交接棒；
- `project-flow 预算 [STOP]`：禁止继续扩展实现或大范围探查，先落盘现有成果、写 `flow/进展.md` 顶部交接棒，并把 `flow-budget.py` 输出的接力提示词交给新会话。

交接棒必须写全四字段，缺一视为未交接（`flow-boot.py` 会在下一轮开工时拦出）：

```markdown
## YYYY-MM-DD · <任务> · <谁>
- 现状: <已做到哪，具体到文件路径或 Exit 0 命令>
- 还剩: <未完成项清单>
- 卡在哪: <熔断原因 / 缺什么 / 无>
- 下一步: <接手方第一条具体命令>
```

单条交接棒控制在 1200 字节内；只写现状、剩余、阻塞与下一步，不复述背景。

### 4. 交付验收卡

完成后给出改动文件绝对路径、验证命令与 Exit 0 证据；需人工确认时补 Given-When-Then。

### 5. 收工写进展

每轮结束前在 `flow/进展.md` 顶部追加一条（做了什么/为什么/怎么理解/产出路径/问题→解决/下一步），只留最新 1~2 条。

### 6. 边界

- 当前用户指令高于历史 plan；子 Agent 不读写 `flow/`，只交付文件与测试结论。
- 不允许以文档代替代码，不允许未验证就宣称完成；不安装 Hook。

### 7. 按需加载与遗留暴露

- 只读取 `flow/plan.md` 的 `[ ]`/`[✕]` 与 `flow/进展.md` 顶部 1 条；`[-]`、`flow/history/`、`flow/trash/` 默认静默。
- SDD/TDD/ATDD/BDD、Plan 模式、初始化、归档、热同步等长规范放在 `flow/规范/`，按当前任务类型加载，不塞回 AGENTS.md。
- 无 Hook 时的“主动”定义为每次用户输入后的首动；无用户输入不会后台执行。无人值守任务必须由外部 automation 触发。
- 安全范围内的验证临时目录和过长交接日志由 `flow-boot.py` 自动回收至 `flow/trash/verification-gc/` 或 `flow/history/`；业务交付物、任务卡和源码不会自动删除。
- 阶段唯一映射：`plan`＝项目初期 Plan / Goal / SDD，`execute`＝实现期 TDD，`review`＝验收期 ATDD，`handoff`＝收尾期 BDD；单向流转，不跳阶段。
- 复杂任务先创建 `flow/tasks/<ticket>.md`，按《计划模式交接SOP.md》决定交给 Codex Plan Mode 还是直接 Execute Mode；不把“已规划”或“已交接”当作“已交付”。

<!-- project-flow-cy:end -->

---

## 项目知识

（本项目的业务规则、命令、目录说明追加在此处，热同步不得覆盖。）
