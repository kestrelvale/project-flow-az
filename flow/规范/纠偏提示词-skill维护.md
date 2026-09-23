# 纠偏提示词（skill 维护专用）· 2026-09-24

**用途**：贴给「继续开发 / 维护 project-flow 这个 skill」的会话。
它和 `references/纠偏提示词.md`（面向分端业务会话）不是一回事：这份管**改 skill 本身**。

**当前唯一正式位置**：`/Users/chinkinoko/projects/project-flow-az`
（`~/.codex/skills/project-flow-az` 软链指向它；当前版本 4.15.13）

```text
【纠偏指令 · project-flow skill 维护 · 立即生效】

0. 位置（最重要，先纠正）
   - 唯一正式仓库：/Users/chinkinoko/projects/project-flow-az
     （Codex 会话使用的 ~/.codex/skills/project-flow-az 是软链，指向它）
   - 禁止在 /Users/chinkinoko/projects/ai-hardware/project-flow-cy 修改 skill：
     那是 ai-hardware 项目根下的子目录，已被取代；在那里改会造成两份分叉，
     会话用的是软链那份，你改的是旧那份 -> 改了不生效。
   - 第一件事就是 cd 到正式仓库，确认 git rev-parse --abbrev-ref HEAD 是 main、
     VERSION 是最新，再开始任何改动。

1. 硬首动（每个执行型回合第一条工具调用）
   python3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent "<本轮任务>"
   该仓库已有 flow/ 控制面，必须被接管：报当前聚焦、路由、预算等级、是否柔性阻塞、
   未回收规格点。若报「未接管」，说明你站错了目录，回到第 0 条。

2. 唯一待办源
   - flow/plan.md 的活跃区（[ ] / [✕]）
   - flow/specs/<ticket>.md 里状态不是 [x] 的规格点
   只做未回收项；标记 [x] 的完成项不得重跑。没有对应卡就**先建卡**
   flow/tasks/<ticket>.md（schema: v2），再动手；复杂需求先在 plan.md 登记。

3. 改动闭环节奏（缺一步都不算完成）
   - 改代码 -> bash tests/run-all.sh 必须全绿（当前 16 项）
   - 更新 CHANGELOG.md：**只能 prepend，禁止覆盖写**（v4.15.4 曾把 41 段历史截成 1 段并已推送）
   - bump VERSION（例如 4.15.13 -> 4.15.14），版本号必须等于 CHANGELOG 顶部那条
   - git push origin main（这个仓库是用户明确授权可推的；业务项目一律不许推）
   - 收工写 SDD 蒸馏交接棒到 flow/进展.md 顶部，并回收本次涉及的规格点

4. 机制红线（改 skill 时不得破坏）
   - 交接棒标题必须带 `· thread=<CODEX_THREAD_ID>`；只有当事会话能核销自己的熔断
   - 交接棒只写「规格点 SPE-n / 待办 / 证据 / 下一步」，禁止原样照抄用户消息
     （判据：最长连续照抄 >= 400 字符或比例 >= 60% 即不合格）
   - 熔断（STOP）时必须把 flow-budget 输出的「project-flow 接力提示词」原样贴进回复，
     再结束本轮；只写「已熔断」不算交接（机检 task_complete.last_agent_message）
   - 规格点台账 `[x]` 必须带证据，假销账会被 review/handoff 门禁与 flow-deliver 拒绝
   - 预算口径：WARN = 有效窗口 45% / STOP = 50%（比例，随模型的 model_context_window 自适应）
   - 中段复查：每 50 次工具调用跑一次 flow-budget.py --guard --project .
   - 不装 Hook（AGENTS.md 明令）；不启停业务服务；不动业务仓库

5. 判断「缺什么就做什么」的口径
   先跑 flow-boot 看它点出的阻塞与未回收项；再看 tests/ 里是否有覆盖该行为的回归。
   没有回归就补一条能失败的测试（先红后绿），再改实现；改完把卡与台账销账。

6. 收工汇报格式
   做了什么 / 为什么 / 产出路径 / 证据（Exit 0 原文）/ 阻塞 / 下一步。
   交付类任务还要跑 flow-deliver.py，并把三段（看板 + 工作汇报 + 交付验收卡）原样粘贴。
```

**为什么要有这份**：2026-09-23 实测踩过两次同一类坑——会话开在了旧 checkout
（`ai-hardware/project-flow-cy`）或临时会话目录，`flow-boot` 报「未接管」，
于是没有路由/没有门禁/没有交接协议，任务做到一半就断，接替者也不知道从哪继续。
