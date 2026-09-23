## [4.15.5] - 2026-09-23 (修复「要求交接却没有交接提示词」)

### 诊断结论（用户反馈 + 本机取证）
用户贴完纠偏提示词后反馈：**该交接了，但拿不到交接提示词**。核查近 6 小时 10 个 rollout：
`接力提示词` 出现 137 次、`柔性阻塞` 191 次——提示词没消失，但**两条路径上取不到**：

| 路径 | 事实 | 证据 |
|---|---|---|
| 中段复查 `--guard` | STOP 时只印一句「动作：把规格点蒸馏进…」，不含可复制的提示词 | guard 分支源码 + 会话输出 |
| 熔断回执 | 回执里**存着** 973 字符的 `handoff_prompt`，却**没有命令能读回来** | `zhengjie-hrm/flow/budget/20260923-181201-stop.json` |
| 开工柔性阻塞 | 只说「必须补写交接棒」，没把回执里那份提示词贴出来 | `render_stop_reports` |

### Fixed
- **`flow-budget.py --print-relay`（新）**：按需打印可复制的接力提示词，**优先取最近熔断回执里存的那份**；
  没有回执时按当前会话实时生成；不判级、不写回执。
- **中段复查带上提示词**：`--guard` 非 OK 时，在「动作」之后直接附完整接力提示词。
- **开工即给提示词**：`flow-boot.py` 熔断交接段把回执里存的提示词原样贴出。
- 纠偏提示词文档补上取回命令。

### Fixed (事故回填)
- **`CHANGELOG.md` 历史被截断**：v4.15.4 提交（`1dea9ca`）误用覆盖写，把 49153 字节 / 41 段
  历史截成 2658 字节 / 1 段，且已推送远端。本版从 `e943440` 取回完整历史并重做 4.15.4 / 4.15.5 两条。
  回归由 `tests/test-multi-project-structure.sh` 抓到（要求 CHANGELOG 含 `### Packaging`）。

### Verification
- `tests/run-all.sh` 全量 13 项 Exit 0；`test-flow-budget.py` 新增断言：`--guard` STOP 必须含
  「project-flow 接力提示词」与 `--intent`；`--print-relay` 必须带出来源回执（`stop.json`）。
- 真实项目验证：对 `~/projects/zhengjie-hrm` 执行 `--print-relay`，取回
  `20260923-181302-stop.json` 里那份提示词（含 `--intent "P3 交接落盘校验（回执复核）"`）。
- CHANGELOG 完整性：`grep -c '^## \[' CHANGELOG.md` 应 > 40（本次为 42 段）。



## [4.15.4] - 2026-09-23 (外部预算心跳 + 心跳自身两处真 bug 修复)

### Added
- **`flow-heartbeat.py`（外部预算心跳）**：扫描近 N 小时活跃的 project-flow 会话，
  逐个算预算；越过 WARN/STOP 就发 macOS 系统通知 + 追加 `~/.codex/project-flow-heartbeat.log`，
  30 分钟内同会话同等级去重。**能力边界（诚实声明）**：外部进程**不能**往会话里插消息——
  那需要 Codex app 的调度器；本心跳解决的是「该交接了要让你看见」，而不是自动替你交接。
- `assets/templates/com.projectflow.heartbeat.plist` + 已装到
  `~/Library/LaunchAgents/com.projectflow.heartbeat.plist`（StartInterval 900，即每 15 分钟）。
  卸载：`launchctl unload -w ~/Library/LaunchAgents/com.projectflow.heartbeat.plist`。
- `flow-budget.py --read-only`：只读模式，不写熔断回执也不写检查点——外部巡检必须无副作用，
  否则后台任务会往你每个项目的 `flow/budget/` 里灌文件。

### Fixed（心跳自身，均为实测发现的真 bug）
| # | 缺陷 | 证据 | 修法 |
|---|---|---|---|
| 1 | thread_id 解析错误（被时间戳前缀带偏） | 日志出现 `23T01-43-20-` 这种值，预算读数为 `输入 0/0` | 改用 UUID 正则从文件名提取，并加回归测试 |
| 2 | 解析失败被当成告警写入日志 | 日志出现 `[None] ... 输入 0/0 ... 轮次 None` | `level` 不在 {OK,WARN,STOP} 直接跳过，不写日志 |
| 3 | 去重状态被并发实例互相覆盖 | `launchctl kickstart -k` 杀旧实例后，状态表被冲成只剩 1 个键 → 同批会话反复通知 | `save_state` 改读-合并-原子写（tmp + replace），并加回归测试 |

### Verification
- `tests/run-all.sh` 全量 **13 项 Exit 0**（新增 `test-flow-heartbeat.py`）。
- **计划任务实跑验证**：`launchctl kickstart -k` 后，进程由 launchd 自行拉起并写出
  去重状态文件（17:38），日志追加新时间戳；`launchctl list` 显示 `com.projectflow.heartbeat` 已注册、上次退出码 0。
- **只读验证**：心跳运行前后，`~/projects/zhengjie-hrm/flow/budget/guard.json` 的 mtime 不变。

### Docs
- OCR（open-code-review）复用中继端点的结论（2026-09-23 实测，逐条有证据）：**当前不可用**——
  25820（WOYAO 本地代理）429 额度耗尽；Lzh 502「upstream access forbidden」；MiniMax/1mmc 401 密钥无效；
  feichuangtech/fengwind 403；TeamoRouter 余额不足；OpenRouter 该模型已下线；
  25817（Codex 专用）明确返回 `api_key_not_supported`。OCR 配置命令已备好，等一个有额度的 key。

## [4.15.3] - 2026-09-23 (规格点台账成为进出 review 的硬门禁 + 中段复查强制化)

### Added
- **规格点台账硬门禁**：`flow-gate.py` 在 `review` / `handoff` 阶段强制校验
  `flow/specs/<ticket>.md`——台账缺失、格式不符、**有空编号**、**`[x]` 无证据（假销账）**、
  仍有未回收项，一律拦下。确实无规格点的琐碎卡必须显式写 `spec_ledger: none`（留痕豁免，
  不是静默放行）。依据：P0/P4 会话中断后同一个需求点被反复执行，根因就是没有销账台账。
- **台账可用自定义路径**：`spec_ledger:` 写相对项目根的路径即按该路径校验（默认
  `flow/specs/<ticket>.md`），且必须落在项目内。
- **出厂台账模板** `assets/templates/flow/specs/TEMPLATE.md`：把行格式、状态语义、
  硬规则与「不许原样照抄用户原话」写进新项目。
- **任务卡模板**新增 `spec_ledger:` 字段与 Plan 阶段的规格点产出项。

### Changed
- **中段复查从「可被调用」升级为「可被强制」**：`flow-budget.py --guard` 现在写一份
  **覆盖式**检查点 `flow/budget/guard.json`（记录当时的工具调用数）；`flow-boot.py` 在开工时
  比对「距上次检查点是否已过 50 次工具调用」，过期即纳入**柔性阻塞**（路由降级 handoff-only）。
  依据：P4 在**同一个 turn 内**跑了 200+ 次工具调用，开工那一次判定（当时仅 38%）早已过期。
- 柔性阻塞提示不再写在 `if stop_reports` 分支内——否则「只有复查过期」时线号是空的。
- 预算子进程改为只跑一次（先捕获、末尾原样打印），用它同时服务复查过期判定与输出，
  不再为拿工具调用数重复解析 rollout。

### Boundaries
- **Hook 仍然不装**（AGENTS.md 明令）。因此中段复查的强制时点是「下一个可观测入口」
  （开工/门禁/交付），**不是**工具调用之间的实时拦截；真正的中段实时拦截需要 `post_tool_use`
  hook，属于用户明确排除的范围。
- **心跳 automation 未能落地**：`automation_update` 在本会话未加载（`unsupported call`），
  本机也没有任何 automation 存储（`~/.codex/automations` 不存在、`state_5.sqlite` /
  `thread_history_1.sqlite` / `queue_1.sqlite` 均无相关表），无格式可依、不可臆造。三次途径
  全部受阻，按熔断止损停止尝试并上报。

### Verification
- `tests/run-all.sh` 全量 **12 项 Exit 0**（新增 `test-spec-ledger-gate.py`）。
- 新增负向回归：台账缺失 / 未回收 / 假销账必须拦；全部回收且带证据必须放行；
  `spec_ledger: none` 必须放行；`--guard` 超线必须非零；检查点过期必须触发柔性阻塞。

## [4.15.2] - 2026-09-23 (阈值 45%/50% 落地 + 执行逻辑 TDD/ATDD 审查)

### Changed
- **用户拍板**：`WARN = 45%` / `STOP = 50%` 有效窗口（此前 34% / 45%）。绝对值兜底同步为
  42 万 / 47 万（按实测中继窗口 950k 换算）。**知情取舍**：50% 时距实测失效起点（58.5%）
  只剩 8.5% 窗口 = 950k 下 8.1 万 tokens，而单轮增量 p90 = 12.5 万，余量约 0.65 个 p90 轮
  （45% 时为 1.03 个轮）。

### Fixed（本轮自审发现并修复的真实缺陷）

| # | 缺陷 | 证据 | 修法 |
|---|---|---|---|
| 1 | **柔性阻塞可被一句话绕过**：核销只比对「顶部交接标题是否变了」 | 实测写 `## 2026-09-23 · T1 · 交了` + `- 干了点活` 即解除阻塞，机制形同虚设 | 核销门槛升级为「标题变了 **且** 通过蒸馏/字段校验」（`handoff_is_acceptable`），并加回归测试 |
| 2 | **照抄检测被静默关闭**：核销链路给 distill 传硬编码假 thread-id | 比对源为空 → 照抄检测恒真 | 打通真实 `CODEX_THREAD_ID`（含环境变量兜底），并在缺 id 时**判失败**而非通过 |
| 3 | **中段复查根本没实现**（此前只是方案里的承诺） | P4 在同一 turn 内跑 200+ 次工具调用，全程无第二次预算判定 | 新增 `flow-budget.py --guard` + 开工输出写入「每 50 次工具调用复跑」节奏 |
| 4 | **回执可被噪音淹没**：`--guard` 若也写熔断回执 | 每 50 次调用刷一条 → `flow/budget/` 重复回执堆积、「最近一次 STOP」判定失真 | `--guard` 不写回执，回执只由开工判定负责 |
| 5 | **规格点台账串票**：`spec` 校验未按 ticket 过滤 | 一个 ticket 的假销账会错报成另一个 ticket | `--ticket` 透传（`flow-deliver` 已按 ticket 传） |

### Verification
- `tests/run-all.sh` 全量 **11 项 Exit 0**。
- **真实数据 ATDD**：把 P4 会话真实的 12942 字符回放块（`task_complete.last_agent_message`）
  当作交接棒喂进护栏 → **Exit 1**，判出「原样照抄用户消息（照抄比例 26%、最长连续 958 字符）」；
  同一线程换成 SDD 蒸馏交接棒 → Exit 0。真实数据双向验过。
- 由此确认**主判据是「最长连续照抄 ≥400 字符」**：P4 的块照抄比例只有 26%（边叙述边摘抄，
  比例被稀释），单靠比例会漏判。已在代码注释与本节写明，防止后人误删。
- 新增回归：空洞交接棒不得核销、`--guard` 超线必须非零、未超线必须零。

## [4.15.1] - 2026-09-23 (预算阈值改为窗口相对，锚定实测失效起点)

### 诊断结论（有实测依据）

4.15.0 把 STOP 拍成 28 万绝对值，经复核**是错的**：窗口不是常量。
Codex 的有效窗口 = 模型 `context_window` × `effective_context_window_percent`，
即会话里的 `model_context_window`：

| 事实 | 证据 |
|---|---|
| 中继会话统一声明 950000 | `~/.codex/sessions/2026/09/**` 里 307 条 `model_context_window` 全为 950000（=0.95×1e6） |
| 连目录写 272k 的模型也报 950k | `gemini-3.8-flash` 会话同样报 950000 |
| 原生 GPT 才是 258400 | 2026-05 的 `gpt-*` 会话报 258400（=0.95×272k） |
| 压缩触发点 ≈ 104.9% 窗口 | 一次请求输入 996370 时 `compacted` 才安装成功 |
| **先失效的是模型，不是压缩** | deepseek-v4.1-flash 在 556166/574491/608167 连续三次放弃干活、把用户消息原样回放成汇报（=58.5% 窗口） |
| 单轮增量实测 | p50 30982 / p90 125246 / max 289972 |

所以 28 万这个数对 272k 模型（有效 258.4k）**永远晚于压缩**，对 950k 模型又偏紧。

### Changed
- **阈值改为窗口相对**：`STOP = 45%` 窗口、`WARN = 34%` 窗口，推导 = 实测模型失效起点
  58.5% − 一个 p90 轮 13.2%。落到各模型：258400 → 11.6 万 / 190000 → 8.6 万 /
  353400 → 15.9 万 / 950000 → 42.8 万。
- 绝对值（WARN 32 万 / STOP 43 万）**只在 session 缺 `model_context_window` 时兜底**，
  不再与比例判级并列触发。
- 轮次/工具调用上调为 WARN 15 / STOP 25 与 90 / 160，只作漂移兜底，不再抢在 token 线前面报。
- 新增 `MODEL_FAILURE_RATIO = 0.585`，记录实测失效起点，供提示文案与标定锁引用。

### Verification
- `tests/run-all.sh` 全量 11 项 Exit 0。
- `test-flow-budget.py` 的标定锁升级为**三条推导约束**：`STOP_RATIO < MODEL_FAILURE_RATIO`；
  `STOP_RATIO × 950000 < 556166`；`(1 − STOP_RATIO) × 258400 ≥ 125246`（272k 模型必须
  留出 ≥1 个 p90 轮余量）。任何把阈值拍回绝对值的改动都会在这里失败。

## [4.15.0] - 2026-09-23 (规格点回收台账 + 交接棒 SDD 蒸馏 + 柔性阻塞)

### 诊断结论（有实测依据）

用户反馈「有几个会话汇报时把**所有用户消息**带上了」。逐条解析 8 个分端会话的
rollout（`~/.codex/sessions/2026/09/{21,22}`）后：

| 事实 | 证据 |
|---|---|
| 回放块只出现在 2 个会话 | P0 `01a0c24b` 3 次、P4 `01a0c1cd` 3 次；P3 `01a0c1cb`、P-FRONT-* `01a0c6f8` 均为 **0** 次 |
| 出现处都不是报告，而是**压缩产物顶替了回复** | P4 第 2192 行 `task_complete.last_agent_message` = 12942 字节的「1. 主要请求与意图…」块 |
| 触发条件是上下文进入压缩区 | 回放块处单次输入 556166 / 574491 / 608167（窗口 950k） |
| 压缩**安装成功**的会话没有回放块 | P3 `compacted`×1、P-FRONT-* `compacted`×2 → 产物是规范短交接摘要 |
| 熔断触发层一直是正常的 | `预算 [STOP]` 出现次数：P3 16、P-FRONT-* 11、P0 7、P4 2 |
| 强制层完全缺失 | `stop_reports` / `handoff_problems` 只被 `print`，`budget_code` 退出码无人消费 → 会话继续跑到 608k |

根因不是「汇报模板带了用户消息」——`flow-deliver.py` 不含任何历史消息回放，
而是**会话没在熔断线交接**，一路进压缩区；压缩产物又只是把用户原话原样复述，
既没有规格点也没有销账，新会话只能重读全部历史。

### Added
- **`flow-distill.py`（新）**：两道校验。
  - `spec`：校验 `flow/specs/<ticket>.md` 规格点台账。格式错、编号重复、
    **标记 `[x]` 却没有证据（假销账）** 一律 Exit 1；正常时输出回收表与未回收清单。
  - `handoff`：校验 `flow/进展.md` 顶部交接棒是否为 SDD 蒸馏产物——
    缺「规格点/待办」结构，或与用户消息的照抄比例 ≥60%、最长连续照抄 ≥400 字符，Exit 1。
- **规格点回收进汇报**：`flow-deliver.py` 自动读取本 ticket 的台账，在交付三段中插入
  `### ♻️ 规格点回收`（每条状态 + 未回收计数）；台账不合格时**拒绝交付**（Exit 1）。
- **柔性阻塞**：`flow-boot.py` 检测到未核销的熔断回执时，路由降级为 handoff-only
  （`route_hint` 只出交接提示、跳过意图认领、`render_sdd_gate` 拒绝登记新意图），
  并在开工状态里打印 `【柔性阻塞】`；**进程不失败**，补上交接棒后自动解除。
- **开工输出规格点回收**：把未回收规格点作为「续跑唯一待办源」贴在接管路由前，
  明确「标记 `[x]` 的完成项不得重跑」。

### Changed
- **预算阈值按实测重标**（压缩区实测起于 556k，窗口 950k）：
  `WARN 180k / 18% / 15 轮 / 90 次工具调用`，`STOP 280k / 29% / 22 轮 / 150 次`。
  旧值 `工具调用 ≥100` 曾在单次输入仅 38% 时误报 STOP（P4），熔断被降级成噪音。
- **交接模板改为 SDD 蒸馏**：`flow-budget.py` 的接力提示词给出交接棒与规格点台账
  模板（SPE-n / 待办 / 证据 / 下一步），并显式禁止把用户消息原样贴进交接棒或汇报。
- WARN 处置改为「回上游 SDD/plan 拆卡」，不再把加大读取当解法。

### Boundaries
- 柔性阻塞不改变既有进程失败语义（未接管仍 Exit 1）；它约束的是**路由与意图登记**，
  不是杀进程。
- 无法阻止 harness 在压缩时输出回顾块（那是 Codex/压缩链路行为）；本版保证的是
  **会话在 28 万 token 就交接、不再进入压缩区**，以及交接物必须是可销账的规格点。

### Verification
- `tests/run-all.sh` 全量 **11 项 Exit 0**（新增 `test-flow-distill.py`、
  `test-flow-soft-block.py`）。
- `test-flow-budget.py` 增加**标定锁**：`STOP_INPUT_TOKENS` 与 `STOP_RATIO × 950k`
  必须小于实测压缩区 556166，防止阈值再漂回压缩区之后。
- 负向回归：假销账、台账格式错、原样照抄交接棒必须 Exit 1；补上规范交接棒后
  柔性阻塞必须自动解除。

## [4.14.0] - 2026-09-23 (收工看板落盘回执 + 开工回执门禁)

### 诊断结论（有实测依据）

用户反馈「看板又没了」。核查 `codex-threads/01a0c8a1`（cwd `o2o-shopping`）的
session jsonl：

| 事实 | 证据 |
|---|---|
| `flow-deliver.py` 确实跑过 | 该 session 出现 7 次 `flow-deliver.py` 工具调用 |
| 看板从未进用户可见回复 | 523 条助手消息里，含“任务状态看板/本轮工作汇报/交付验收卡”的为 **0** 条 |
| 规则本身在场 | AGENTS.md 的“收工再报验收”在该 session 里出现 5 次 |

根因不是规则缺失，是**规则只存在于自然语言里，没有任何机器校验**：`flow-deliver.py`
的输出只活在工具结果中，模型改写摘要就彻底丢失。

### Added
- **收工回执落盘**：`flow-deliver.py` 除打印外，写 `flow/deliveries/<时间>-<ticket>.json`
  回执与 `flow/看板.md` 副本；结尾打印 `>>> 以上三段必须原样粘贴到回复` 与两处路径。
- **开工回执门禁**：`flow-boot.py` 新增 `## 📨 交付回执`，核对每个 `[-]` 待验收任务的回执，
  输出`有回执 a / 查无回执 b / 编号无法识别 c`；b 或 c 非零时在 `## ♻️ 回收建议`
  点名要求补跑 `flow-deliver.py`。
- 编号识别兼容 `P0-3` 与 `P-FRONT-3` 两种写法；无编号的历史条目按“无法核对”单列，
  不得被当作“有回执”蒙混过关。

### Boundaries
- **不夸大**：无 Hook 时无法强制模型把文本写进回复。本机制保证的是——看板不会随会话消失
  （总有落盘副本），且“漏了收工”会在下次开工被机器点名，而不是变成静默债。
- 开工输出仍然**不含**四分区收工看板（`## ⏳ 待人工验收` / `## 📦 已完结归档` /
  `## 💡 本轮决策记录`），保持“开工状态与收工看板分离”的既有契约。

### Verification
- `tests/run-all.sh` 全量 9 项 Exit 0。
- 新增回归：`flow-deliver.py` 必须落盘回执与看板副本；`flow-boot.py` 对查无回执必须点名，
  补齐回执后必须自动消除；无编号条目必须进入“无法核对”而不是被放过。

## [4.13.2] - 2026-09-22 (交接三段链入文档)

### Docs
- `会话预算与接力SOP.md` 补全**交接三段链**的完整说明，此前只写了 STOP 动作，
  与实现不齐：
  1. **会话内监控** —— `flow-budget.py` 每轮读真实 session usage，判定 OK/WARN/STOP；
  2. **生成接力提示词** —— WARN/STOP 时输出可复制的启动指令（含只读白名单与真实熔断数据）；
  3. **新会话强制校验交接棒** —— `flow-boot.py` 检测 STOP 后校验四字段与 1200 字节上限。
- 补充交接棒标准格式（现状 / 还剩 / 卡在哪 / 下一步）与“为什么要强制”的实测依据。
- 补充**降级行为边界**：`~/.codex/sessions/**` 是客户端自有格式，读不到时脚本返回 0、
  不阻塞施工，仅失去预算预警。

### Verification
- `tests/run-all.sh` 全量 9 项 Exit 0；结构测试新增断言，校验 SOP 字段名与
  `flow-boot.py` 的 `HANDOFF_FIELDS` / `MAX_HANDOFF_BYTES` 一致，防止文档与代码再次漂移。

## [4.13.1] - 2026-09-22 (TDD red_test 防绕过校验)

### Fixed
- **`red_test` 不再只验存在性**：v2 门禁现在要求它指向**真的测试**——
  路径必须落在 `tests/`、`test_*` 或 `*.test.*` 之下，且正文含
  `assert` / `expect` / `test(` / `def test_` 等用例特征。

### Why
- 实测发现旧规则可被 `red_test: README.md` 绕过：只要文件存在就放行，
  等于没有证明“先红后绿”。这是 v2 存在性门禁留下的最后一个明显缺口。

### Compatibility
- 现有 97 张任务卡中仅 6 张为 v2（且全是模板，无真实在途卡），改动零影响；
  老卡不带 `schema: v2`，不触发该校验。

### Verification
- `tests/run-all.sh` 全量 9 项 Exit 0。
- 新增两类反例回归：指向 README 必须 FAIL；路径像测试但无断言必须 FAIL；真测试仍放行。

## [4.13.0] - 2026-09-22 (方法论吸收进模板，skill 按需调用)

### Added
- **任务卡模板吸收四个成熟 skill 的设计**，把 Plan/SDD、TDD、ATDD、BDD 从口号变成可填写结构：
  - Plan/SDD：问题陈述、用户故事、实现决策、测试决策、不做的事（取自 `to-spec`）；
  - Execute/TDD：写明**五拍循环**（写失败测试 → 跑确认失败 → 最小实现 → 跑全绿 → 提交），
    并新增 `首次失败输出（证明它真失败过）` 字段（取自 `test-driven-development`）；
  - Review/ATDD：可执行断言 + 不可自动化部分的可复现命令；
  - Handoff/BDD：Given-When-Then 每条对应一个可观测断言。
- **按需深挖指引**：任务卡末尾列出四个 skill 的绝对路径，结构不够用时再读原文。
- `驱动模式与验证策略.md` 增补 TDD 铁律、三种反模式（实现耦合 / 同义反复 / 水平切片）、
  垂直切片要求，以及四种模式的调用方式对照表。
- 挂载 `writing-plans`、`executing-plans`、`test-driven-development` 三个 skill 到 Codex 技能目录。

### Why
- 用户问“有没有写得好的 skill 可直接复用”。核查确认本机已有成套方法论 skill，
  但其总注入成本约 19KB/任务，且 `to-spec` 强依赖 issue tracker，与本项目文件流不兼容。
- 按奥卡姆剃刀、矛盾论、孙子兵法评估后选择**方案 2**：只吸收模板结构（常驻约 5KB），
  深挖能力按需读取原 skill，避免每次任务重复支付注入成本。

### Verification
- `tests/run-all.sh` 全量 9 项 Exit 0；新增 `tests/test-task-template.py`
  校验模板自带 v2 字段、已吸收方法论，且填充后四阶段门禁全部放行。

## [4.12.0] - 2026-09-22 (理论落地为可验证产物 + 归档回执工具化)

### Added
- **v2 严格门禁**：`schema: v2` 的任务卡由 `flow-gate.py` 校验真实产物，
  把 Plan/SDD/TDD/ATDD/BDD 从“字段里有这个词”升级为“磁盘上必须有这个东西”：
  - Plan/SDD：`scope` 必须写全输入、输出、边界三段；
  - TDD：`red_test` 必须指向真实存在的失败测试文件；
  - ATDD：`evidence` 必须指向真实存在的证据文件；
  - BDD：`acceptance` 必须是 Given-When-Then。
- **任务归档工具化**：`flow-gc.py --task-archive <ticket> --evidence "<证据>" --apply`
  移动任务卡并写出标准 `task_archive` JSON 回执；无证据拒绝归档。
- `audit-flow.py` 新增孤儿回执检测：`history/tasks/` 下无对应 JSON 回执的归档卡会报警。

### Why
- 用户追问“Plan/SDD/TDD/ATDD/BDD 到底怎么规定执行的”。核查确认旧实现只校验
  `method` 字段是否包含 `TDD` 这样的字符串——实测可以造出一张完全没有测试的卡，
  只要写上 `method: TDD` 就过门禁。**理论沦为标签，Agent 每次自行发挥。**
- 9/19 方案里的“任务归档回执工具化”当时未落地，回执靠手写 Markdown，
  格式各异且机器读不了，导致归档三问（归档了没/为什么/什么证据）答不上来。

### Compatibility
- 老卡（无 `schema` 字段）继续走宽松规则，不影响在途任务；
  v2 只对新卡生效，避免一次性推翻全部历史任务卡。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 8 个测试脚本 Exit 0。
- 实测：v2 卡缺 scope 边界 / red_test 不存在 / evidence 不存在 / 非 Given-When-Then 均被拦；
  老卡同内容放行；无证据归档被拒；带证据归档生成可解析 JSON 回执。

## [4.11.0] - 2026-09-22 (日志分页与交接棒结构化版)

### Fixed
- **进展日志分页失效**：`flow-gc.py` 只识别 `## ` 标题，但历史项目实际写 `### `，
  导致 o2o 的进展日志涨到 86KB / 41 条仍未滚动，每次开工全量灌入上下文，
  会话必然在预算耗尽前熔断——这正是“同一任务拆了三四个会话还没做完”的直接原因。
- 分页改为**条数与字节双阈值**：超过 5 条或 12KB 即滚动，保留最近约 6KB。
- 滚动条数统计修正为按实际切点计算，不再误报。

### Added
- **交接棒结构化强制校验**：上一轮因预算 STOP 中断时，顶部交接棒必须写全
  「现状 / 还剩 / 卡在哪 / 下一步」四字段，且单条不超过 1200 字节，
  否则在「路由阻塞」拦出。避免新会话为还原现场重读全部文件、把熔断成本再付一次。
- 新增 `tests/test-flow-gc.py`：覆盖 `### ` 写法与字节超限两类滚动回归。
- 进展模板、`AGENTS.md` 合同与按需加载 SOP 同步四字段交接规范。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 8 个测试脚本 Exit 0。
- o2o 真实进展日志实测：86,664 → 13,040 字节，归档 36 条到
  `flow/history/progress/进展_202609.md`，41 条无丢失。

## [4.10.1] - 2026-09-22 (巨型卡检测补全 scope 维度)

### Fixed
- 巨型卡检测补上 `scope` 维度：范围并列交付物超过 8 项、或范围描述超过 12 行同样判定为巨卡。
- 巨型卡检测不再只看活跃区：未绑定 `plan.md` 的孤儿卡同样会被检出，避免巨卡躲在 `flow/tasks/` 里等开工才暴雷。
- 修复 `read_card` 未收录 `scope` 字段，导致体量检测拿不到范围内容的缺陷。

### Why
- 用户指出前一版分析搞错了项目：那次反复 3 次的是 **o2o 账号角色权限（P0-39）**，不是
  zhengjie-hrm 的企业 Web 样板端。追查后确认 P0-39 的真实病根在 `scope`——
  一张卡塞了 14 项并列交付物（账号唯一、五类身份、RBAC、店员鉴权、扫码登录、密码管理…），
  必然跨多个会话才能勉强推完，永远收不了口。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 7 个测试脚本 Exit 0。
- o2o-shopping 实测检出 3 张巨卡（P0-38 十项交付物、P0-39 十四项 + 五个验收场景、P0-40 范围 14 行）。
- zhengjie-hrm 检出 2 张（P3 验收链 8 段、设计系统白名单 11 条）；easy-input-maker 与 ai-hardware 零误报。

## [4.10.0] - 2026-09-22 (巨型任务卡拆分门禁版)

### Added
- **任务体量门禁**：开工阶段检测“巨型任务卡”，任一项超限即在「路由阻塞」拦出，要求在 Plan 阶段拆成原子卡后再施工：
  - 写入白名单超过 8 条；
  - 验收场景（Given）超过 4 个；
  - 验收链路超过 5 段（`→` 串联环节）。

### Why
- 用户反馈同一任务来回交替 3 次仍无法收口，追问“为什么任务会搞得这么庞大”。
- 实测根因：`P3-ENTERPRISE-WEB-SAMPLE-20260922` 一张卡塞入 38 个页面 + 43 个原型节点 +
  9 步主链（验收链路 8 段），而单会话预算是 100 次工具调用，必然中途 STOP、任务烂尾。
  原实现只有会话预算门禁（事后熔断），没有任务体量门禁（事前拆分），所以巨卡永远跑到熔断才停。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 7 个测试脚本 Exit 0。
- 真实项目复验：zhengjie-hrm 的 P3 卡被抓出（验收链路 8 段）；o2o-shopping 与 easy-input-maker 零误报。

## [4.9.9] - 2026-09-22 (认领按意图收敛)

### Fixed
- 任务认领按本轮意图收敛：一次开工只认领与本轮任务匹配的卡，不再吞掉整条活跃队列。
- 依赖未交付的任务卡不再被认领占位，避免会话抱着做不了的卡空转。

## [4.9.8] - 2026-09-22 (多端并行认领与原生交接版)

### Added
- **任务认领机制**：开工时在 `flow/claims/<ticket>.json` 记录会话占用（默认 12 小时过期），其他会话抢同一张活跃卡时被拦，杜绝多端并行时“任务串线”。
- **前置依赖门禁**：任务卡 `depends_on` 声明的前置任务未归档时，禁止开工。
- **原生模式交接契约**：`plan` 路由交给 Codex 原生 Plan 模式与原生 `goal`，`handoff` 完成后用原生目标收口；明确 project-flow 只做控制面与门禁，不重造规划器。
- 路由输出新增“原生交接”提示，Execute 路由明确 SDD/TDD/ATDD/BDD 是执行要求、不是卡片标签。

### Why
- 用户追问“Plan 模式与 goal 能不能交给 Codex 原生处理”，并指出多端并行死战必须有监管。
- 实测确认：原实现完全没有认领、依赖与原生模式交接；`method: TDD` 只是字符串，不校验真实测试。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 7 个测试脚本 Exit 0。
- 构造验证：会话 A 认领后会话 B 被拦；`depends_on` 未交付被拦；白名单交叉被拦。

## [4.9.7] - 2026-09-22 (并行任务冲突拦截版)

### Fixed
- 修复 `flow-boot.py` 自研第二份解析器不认 YAML 块标量、把 `write_whitelist: |` 读成 `|` 导致并行冲突误报的问题；现在复用 `flow-gate` 单一解析器。
- 块标量改为按行保留，多行路径清单可正确拆分。

### Added
- 新增并行任务冲突检测：同一活跃区里多张任务卡的写入白名单交叉时，在「路由阻塞」中拦出，避免两个执行体互相覆盖同一文件（用户反馈的“任务串了”根因）。
- 控制面路径 `flow/` 与 `docs/reviews/` 不参与冲突判定，避免每张卡互相“重叠”淹没真信号。
- 冲突超过 3 组时收敛输出（摘要 + 前 3 组 + 剩余计数），防止看板被淹没。

### Why
- 用户追问“多任务并行能不能监管、会不会串任务”。实测原实现完全没有并行冲突检测，
  两张卡白名单都含同一文件时静默放行两个并行施工体。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 7 个测试脚本 Exit 0。
- o2o-shopping 实测报出 21 组白名单交叉（真实并行风险），zhengjie-hrm 与 easy-input-maker 无冲突不误报。

## [4.9.6] - 2026-09-22 (控制面膨胀检测版)

### Fixed
- 修复 `plan.md` 归档区写裸 `-` 列表项时状态正则识别不到、已终结内容静默堆积的盲区。
- 新增归档类章节体积检测：占全文 ≥25% 时在「回收建议」强制暴露，并给出剪切指引。

### Why
- 用户反馈“任务只往里塞、从不回收，plan 越滚越大”。实测 zhengjie-hrm 的
  `plan.md` 归档区占全文 43%，但开工审计从未报警，导致控制面持续膨胀、接管内容漂移。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 7 个测试脚本 Exit 0。
- zhengjie-hrm 实测：现报出归档区占比 67%（2353/3488 字节）与 5 张孤儿任务卡。

## [4.9.5] - 2026-09-21 (收工看板固定四分区契约版)

### Fixed
- 修复收工看板“照抄各项目 plan.md 自定义标题”导致汇报漂移的问题：看板现在固定输出四分区，标题与顺序不再随项目变化。
- 修复任务全部归档后看板整块变空的问题：空分区显式输出 `- 无`，归档区显示 `flow/history/tasks/` 已归档张数。
- 修复 `plan.md` 不存在时看板退化成单行报错的问题，改回输出完整四分区。
- 修复决策区把 `decisions.md` 的“背景/影响范围”等章节结构误当决策的问题，只收带决策标签的真实条目。

### Why
- 用户反馈“任务做完后汇报不知道汇报了什么、格式每次都不一样”，根因是看板没有固定契约，而是跟随项目自定义标题，任务清空后必然输出空看板。

### Added
- `flow-deliver.py` 固化 `BOARD_SECTIONS` 四分区契约（当前聚焦待办 / 待人工验收 / 已完结归档 / 本轮决策记录）。
- `assets/templates/plan.md` 与 `assets/templates/AGENTS.md` 同步四分区标题，新项目开箱即对齐。
- 交付卡回归补齐：四分区存在与顺序、任务全清空、`plan.md` 缺失、归档计数四类用例。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 7 个测试脚本 Exit 0。
- 真实项目复验：zhengjie-hrm 待验收 2 项、已归档 48 张；o2o-shopping 焦点 7 项、待验收 5 项，看板均完整且标题统一。

## [4.9.4] - 2026-09-21 (看板解析与回收可见性修复版)

### Fixed
- 修复任务卡 YAML 块标量（`key: >` / `key: |`）被解析成字段值 `>` 的问题；收工交付卡的 `自动验证`、`Given-When-Then`、`scope` 现在读回真实正文，而不是标记符。
- 修复归档卡运行 `flow-deliver.py` 时把 `flow/history/plan.md` 误判为计划路径、导致看板退化成“plan.md 不存在”的路径推导缺陷。

### Added
- 开工状态「回收建议」新增**孤儿任务卡**分区：任务卡已不在活跃区却仍滞留 `flow/tasks/` 时，逐张列出待归档卡号，不再静默堆积。
- 新增 `tests/card_fixtures.py` 共享夹具，并为块标量解析、归档卡看板、孤儿卡暴露补回归用例。

### Why
- 用户反馈“任务做完了但看板没了、任务越堆越多没人回收”，根因是解析缺陷让交付卡字段失真，且孤儿卡只有路由提示、没有回收计数。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 7 个测试脚本 Exit 0。
- 真实项目复现：o2o-shopping 19 张活跃卡现报出 10 张孤儿卡；easy-input-maker 报出 10 项活跃区残留已完成项。
- zhengjie-hrm 归档卡重跑 `flow-deliver.py`，看板恢复正常显示。

## [4.9.3] - 2026-09-21 (四阶段驱动模式接管修复版)

### Fixed
- 修复门禁只认 `objective`、但全局说明要求 `goal`，导致所有任务卡在 `flow-boot.py` 一律 FAIL、整个接管看起来失效的问题。
- 修复 `flow-gate.py` 未真正强制四阶段单向门的问题，`goal` 不再是门禁必填项而是与 `objective` 互为别名，二者至少一个即可。
- 修复收工交付卡把目标字段写死为 `objective` 的问题，新卡 `goal` 现在能正确显示。

### Added
- 固化阶段与驱动模式唯一映射：`plan`＝项目初期 Plan / Goal / SDD，`execute`＝实现期 TDD，`review`＝验收期 ATDD，`handoff`＝收尾期 BDD，单向流转不跳阶段。
- 门禁回归测试补齐四阶段必填字段与 `goal` 别名兼容用例。
- 开工路由直接打印阶段语义，明确“项目初期/实现阶段/验收阶段/收尾阶段”各自该做什么。
- 任务卡模板增加 Plan/Execute/Review/Handoff 各阶段产出区。

### Packaging
- 修复 `.gitignore` 中 `/scripts/` 把引擎本体（`flow-boot.py` / `flow-gate.py` / `flow-deliver.py` 等 8 个脚本，约 1400 行）整体排除出版本库的问题；该规则原意为防止误跑产生的运行时输出，但 `sync-project.py` 从不在目标项目创建 `scripts/`，属于误伤。
- 引擎脚本正式纳入版本控制并补齐可执行位，`git clone` 后不再缺少运行时；此前 README 的 clone 即安装承诺才真正成立。
- 补齐 `*.bak_*` 与 `.pytest_cache/` 忽略规则，替代原来的过度忽略。
- 新增结构回归测试：任一引擎脚本若再次被 `.gitignore` 排除或未入库，测试直接 FAIL。

### Verification
- `python3 -m py_compile scripts/*.py` 与全部 7 个测试脚本 Exit 0。
- 端到端验证 `plan -> execute -> review -> handoff` 四阶段门禁全部通过，跳阶段缺失字段时正确 FAIL。
- 旧 `objective` 单字段任务卡可继续通过门禁与接管路由，不破坏历史项目。
- 全新 `git clone` 后 8 个引擎脚本齐全，用 clone 出来的引擎接管临时新项目：输出 Plan 路由且门禁 Exit 0。
- 已热更新 12 个已接入项目至 4.9.3，任务卡模板均带 `goal` 字段。

## [4.8.4] - 2026-09-20 (待办、决策与回收治理版)

### Added
- 开工状态新增“待人工决策”和“回收建议”分区。
- 待验收积压会明确提示逐项确认后归档或退回修复，不自动替用户验收。
- 活跃区仍有已完成项时提示移入 `flow/history/`。
- 开工状态恢复待验收可见性，完整列出 `[-]` 待验收项。

### Fixed
- 修复 `[-]` 未被任务正则识别，导致待验收数量错误显示为 0。
- 修复项目外 cwd 静默返回成功的问题，现在明确报告“未接管”并返回非零。
- 保持开工状态与收工看板分离，不在开工阶段预填验收、归档或决策。

### Verification
- `py_compile`、路由回归、预算回归、门禁回归、交付卡回归和结构测试全部 Exit 0。
- 17 个已接入项目统一同步到 V4.8.4。

## [4.8.3] - 2026-09-20 (待验收状态可见性修复)

### Fixed
- 修复开工状态待验收计数为 0 的解析缺陷：`[-]` 未纳入任务行正则。
- 开工状态现在全量显示真实待验收项，但仍保持“只看状态、不生成收工看板”的边界。
- 增加 `[-]` 计数回归测试。

## [4.8.2] - 2026-09-20 (接管失败显式化)

### Fixed
- `flow-boot.py` 在 cwd 不属于任何已接入项目时不再静默返回成功，改为明确输出“未接管”并返回非零。
- 开工状态新增真实 `[-]` 待验收计数，但不会生成完整收工看板或伪造验收结果。
- 增加“项目外目录必须显式失败”的回归测试。

## [4.8.1] - 2026-09-19 (开工状态与收工看板分离)

### Fixed
- `flow-boot.py` 开工时不再输出完整四状态看板，改为只读“开工状态”。
- 开工输出不再预填“待人工验收、已完结归档、本轮决策”。
- 完整四状态看板与交付验收卡只在收工、验证留证并准备人工验收时输出。
- 增加开工阶段禁止出现收工字段的回归测试。

## [4.8.0] - 2026-09-19 (会话预算监控与自动接力版)

### Added
- 新增 `scripts/flow-budget.py`，从 `CODEX_THREAD_ID` 对应的 Codex session jsonl 读取真实 token 用量。
- `flow-boot.py` 每轮执行预算门禁：上下文占用 >=75% 或轮次 >=20 进入 WARN；>=90%、单次输入 >=30 万、轮次 >=25 或工具调用 >=100 进入 STOP。
- WARN/STOP 自动输出可复制的 project-flow 接力提示词。
- 新增《会话预算与接力SOP.md》与 `tests/test-flow-budget.py`。

### Changed
- 区分“最近一次请求上下文”与“thread 累计输入成本”，避免把 `turn_token_usage` 误当成单次上下文长度。
- 预算 STOP 会作为 `flow-boot.py` 的失败门禁返回，禁止继续扩展实现。

## [4.7.0] - 2026-09-19 (接管路由与交接卡识别版)

### Added
- `flow-boot.py` 新增 `--intent` 与接管路由输出：聚合当前聚焦任务、递归任务卡、Plan/Execute/Handoff 模式和静默卡。
- 活跃区任务与任务卡的绑定校验，路由阻塞和“本轮意图未登记”会明确暴露。
- 新增 `tests/test-flow-boot-routing.py`，验证 Focus/Backlog、嵌套任务卡、Intent 绑定与模式路由。

### Changed
- Handoff 卡不再被当作执行卡；非活跃的 Execute/Review 卡进入静默，不与当前焦点争抢。
- 全局 `AGENTS.md`、`CLAUDE.md` 和项目运行时合同要求每轮首动带 `--intent` 并消费路由结果。

## [4.6.2] - 2026-09-19 (任务卡占位符门禁)

- `flow-gate.py` 拒绝 `<...>`、`TODO`、`TBD` 等占位字段，避免模板被误判为有效任务卡。
- 增加门禁行为测试并接入多项目结构测试。

## [4.6.1] - 2026-09-19 (Plan 术语修正版)

### Fixed
- 明确 `plant` 指 Codex Plan（计划模式），移除误导性的 PlantUML 表述。
- 版本递增以确保已接入项目同步最新交接规范。

## [4.6.0] - 2026-09-19 (全阶段门禁与 Plan 模式版)

### Added
- **安全验证 GC**：`flow-gc.py` 只处理 `flow/.tmp`、`flow/verification-tmp`、`flow/test-output`、`flow/test-results`，过长 `进展.md` 自动滚动到 `flow/history/`。
- **任务卡门禁**：`flow-gate.py` 校验 Plan、Execute、Review、Handoff 阶段字段，`flow-boot.py` 自动检查 `flow/tasks/*.md`。
- **Plan 模式交接**：新增《计划模式交接SOP.md》和 `flow/tasks/TEMPLATE.md`。

### Fixed
- 将误写的 PlantUML 路由改为用户所说的 Plan 模式。
- 禁止 GC 触碰项目根目录的任意 `tmp` 或业务目录。

## [4.5.0] - 2026-09-19 (硬首动审计与遗留暴露版)

### Added
- **统一开工入口**: 新增 `scripts/flow-boot.py`，从当前目录向上定位 `flow/plan.md`，版本落后时按需热同步，随后执行只读审计。
- **硬首动合同**: 全局 `~/.codex/AGENTS.md` 与 `~/.claude/CLAUDE.md` 要求每个执行型回合第一次工具调用运行 `flow-boot.py .`，审计问题必须先在首屏暴露。
- **按需驱动规范**: 新增《驱动模式与验证策略.md》，按任务类型加载 SDD、TDD、ATDD、BDD 与必要的 PlantUML。

### Fixed
- **遗留审计盲区**: `audit-flow.py` 支持列表与旧版表格计划，能暴露 `ok-yudao`、`video daily`、`zhengjie-hrm` 等项目中未归档的完成项。

## [4.4.0] - 2026-09-18 (AGENTS 单一合同版)

### Added
- **全局接管条款**: `~/.codex/AGENTS.md` 与 `~/.claude/CLAUDE.md` 各增加一句接管条件：工作根或父目录存在 `flow/plan.md` 即进入 project-flow 交付模式，无需用户点名 skill。

### Fixed
- **合同丢失根因**: 取证显示 `AGENTS.md` 在会话启动与文件变更时注入，zhengjie-hrm 出问题的前 3 轮注入内容确无运行时合同。根因是合同当时尚未写入项目入口，而非缺 Hook。
- **同步覆盖范围**: 热同步只维护 `project-flow-cy:start/end` 标记块，块外项目自定义内容一律保留；17 个已接入项目合同覆盖 100%。

### Removed
- **奥卡姆剃刀去重**: 删除项目 `AGENTS.md` 中重复的行为准则四条（10 个项目共减约 11KB），行为准则只保留在全局入口一份；运行合同块由 2474B 精简至 1721B。
- **Hook 彻底移除**: 删除用户级 `project-flow-guard.sh` 与其 `SessionStart` / `UserPromptSubmit` 挂载，恢复无 Hook 架构。

## [4.3.0] - 2026-09-18 (无 Hook 轻量化运行时合同版)

### Changed
- **彻底移除 Hook 控制面**: project-flow 不再安装、同步或依赖 `.hooks/`、`.claude/settings.json`、`.codex/hooks.json`；
- **恢复运行时合同**: 每轮首屏看板、四状态机、`plan.md` 同步、验收卡与收工进展重新写回 `assets/templates/AGENTS.md`，并由热同步按 `project-flow-cy:start/end` 标记块维护，不再整文件覆盖；
- **同步器收窄职责**: 只维护 `flow/`、`docs/`、控制面基础文件与 `AGENTS.md` 合同块；
- **测试切换**: 删除失效的 Stop Hook 单测与 TUI E2E，改为校验无 Hook 运行时合同、模板和评测结构一致性。

### Added
- **Gemini 零缓存中转硬熔断门禁 (Gemini Zero-Cache Hard Ceiling)**:
  - 针对 Gemini 系列中转链路实测 0% 缓存导致的 10~12 倍费用滚雪球顽疾，正式确立物理级硬熔断红线；
  - 只要模型为 Gemini：单会话严格 ≤25 轮、累计上下文严格 <10 万 Tokens、单任务工具调用严格禁止超过 100 次；
  - 达到临界区强制禁止继续编码，必须将当前成果物理落盘并向 `flow/进展.md` 写入接力棒；
  - 输出标准化【开箱即用新会话接力提示词模板】，提示用户复制开启全新会话接力。

## [4.2.0] - 2026-09-17 (Delivery-First & 会话平滑接力防膨胀版)

### Added
- **Delivery-First 交付决胜体系**: 引入《项目交付物与交付契约SOP.md》，建立项目交付物法定总账 (`flow/deliverables.md`) 与外部大盘 (`docs/DELIVERY_PREVIEW.md`)，彻底消除任务完成但产物脱节顽疾；
- **零污染治理规范**: 引入《工作区与根目录零污染治理规范.md》，强制四区隔离与根目录绝对纯净；
- **会话平滑接力协议 (Session Relay SOP)**:
  - 确立 20~25 轮会话深度熔断警报卡；
  - 确立标准化开箱即用新会话接力提示词模板（带磁盘真理源、SDD 规格清单、写入白名单锁），实现零上下文包袱极速接力；
- **两级图谱按需定位前置门禁**:
  - 业务概念与规则严格优先检索 `knowledge/index.md` (OKF 知识图谱)；
  - 源码与符号严格优先使用 `codegraph explore` 毫秒级符号定位；
  - 严禁全盘裸扫与大文件大段翻读，杜绝单步 30 万 Token 恶性膨胀；
- **彻底切除 Ruflo 外部依赖**: 废黜依赖 Anthropic Key 的 Ruflo 插件，全面基于磁盘物理契约自闭环。

## [4.0.1] - 2026-09-05 (全自动无感物理热同步落地)
### Added
- **Hook 级全自动热同步 (Zero-Manual Hot-Sync)**: 在全局 `~/.codex/hooks.json` 与项目 `.codex/hooks.json` 中配置 `SessionStart` 和 `UserPromptSubmit` 自动执行 `flow-sync.sh`；
- **开箱即用**: 用户启动会话或发送任何 Prompt 时，系统底层自动在 0ms 内静默比对版本并物理热更新，彻底解决“改了 Skill 却需要手动跑脚本更新”的痛点。

## [4.1.0] - 2026-09-07

### 新增与强化 (Enhanced & Living Steering)
- **主任务恒定推进原则 (Maintain Master Mission)**: 明确用户中途打断属于“航向纠偏与参数校准”（如补充 MCP、更换测试载体），绝非推翻主任务；主目标恒定推进到底。
- **严格停止条件**: 任务本身不可中途自发停止，唯有用户明确发出“做得不对，完全废弃/停止”时方可终止主任务。
- **动态纠偏与即时注入**: 收到纠偏或新参数，立即无缝融入当前执行路径；收到追加需求，动态扩充进待办看板。
- **遇阻熔断汇报 (Blocker Escalation Gate)**: 连续 2 次尝试走不通强制立即停手汇报，严禁编写 AppleScript 乱点等旁门左道。
- **职责彻底解耦**: 将项目管理状态机归属于 Skill，全局 AGENTS.md 仅作为用户个人交互宪法轻量注入。

## [4.0.0] - 2026-09-05 (终极战略驱动设计决胜版)
### Added
- **四大哲学思想全景融合**: 深度融合奥卡姆剃刀（去臃肿/3文件3步骤1铁律）、Ask-Matt（Smart Zone 150k边界/单票独立会话/Disposable Context）、孙子兵法（兵贵神速/探查预算≤3步/避实击虚）与矛盾论（主要矛盾第一/代码落地优先/具体问题具体分析）。
- **四大先进驱动设计全链路贯通**:
  - **SDD (规格驱动设计)**: 复合多需求原子化拆解（P0-1, P0-2...），锁死 I/O 契约与写入边界白名单 (Disjoint Write Sets)；
  - **TDD (测试驱动开发)**: Defect-First 先写/跑失败用例，Ponytail 极简代码落盘使测试变绿；
  - **ATDD (质量准入门禁)**: 确立专属微测试 <3s、Exit 0、0 PageError、截图存盘的自动化准入四要素；
  - **BDD (行为驱动交付)**: 提请验收卡强制采用 Given-When-Then 场景化步骤，用户确认后物理剪切至 `flow/history/` 彻底结案。
- **单会话绝对隔离与白名单切片过滤 (Domain Queueing)**: `flow/plan.md` 永远只存 1 组当前 P0 焦点（< 200 Tokens），多模块任务分卡独立维护，彻底阻断历史任务复读。
- **探查预算门禁 (Probe Budget ≤ 3)**: 禁止无休止 Bash 扫盘，通过 CodeGraph 毫秒级定位。

## [2.3.0] - 2026-09-04
### Added
- **会话健康度监控与自动接力预警 (Session Relay & Context Health Gate)**: 在 `stop-doccheck.sh` 与 `AGENTS.md` 中内置轮次计数器与 Token 阈值熔断机制；
- **智能截断防御**: 当单会话交互达到 8~10 轮临界区时，自动在 Stop Hook 与交付卡中输出【会话熔断预警】，提示用户开新会话轻装接力，彻底杜绝模型因上下文超载发生语法退化与工具截断；
- **知识答疑与机理阐明**: 明确区分“磁盘物理文件回收 (GC)”与“单会话内存追加 (Append-Only)”的技术本质差异。

## [2.2.0] - 2026-09-03
### Added
- **Sub-Agent Swarm 多 Agent 并行协作体系**: 引入 Orchestrator 调度总控与 Worker 隔离执行模型，支持 `spawn_agent` / `wait_agent` 派发前端、后端、测试、深度调研子 Agent。
- **写入作用域完全隔离 (Disjoint Write Sets)**: 强制要求多子 Agent 并行修改代码时文件交集为空，防止代码冲突与并发脏写。
- **控制面单写门禁 (Single Ownership of flow/)**: 严禁子 Agent 修改 `flow/` 目录，由主控 Agent 统一维护四状态机与进展日志。
- **代码落地硬门禁 (Code-First Gate)**: 凡涉及功能开发/修复需求，严禁以纯写方案文档代替代码落地，必须有实际文件修改与自测试。
- **Stop Hook 任务完整性反查机制 (Execution Completeness Gate)**: 收到收工自检拦截时，强制反查未完成代码子项与子 Agent 状态，彻底根除“半路交卷”、“收工自检误当完工信号”的问题。
- **SOP 文档**: 新增 `references/Sub-Agent多Agent并行协作SOP.md`，更新 `references/hook机制.md`。

# Changelog

All notable changes to `project-flow-az` will be documented in this file.

## [v1.1.0] - 2026-08-28

### 🌟 核心架构升级 (Major Architecture Shift)

本项目基于原作者 `CY-CHENYUE/project-flow-cy` 进行深度魔改与治理重构，专门解决大模型在多轮交互中“**历史任务死循环复读、缺乏即时回收、上下文全量污染、旧计划绑架当面指令**”等工程顽疾。

### 🚀 新增特性与机制 (Features & Enhancements)

1. **用户即时指令第一优先级 (Prompt Priority)**
   - 确立“用户当前对话下达的指令高于一切历史计划”铁律。
   - 纠正教条主义：代码与产出必须落盘文件，但绝不能用旧文件反客为主推翻当前指令。

2. **任务四状态闭环流转 (4-State Task Machine)**
   - `[ ]` **待完成 (TODO)**：当前对话指令 P0 最高优先级；规划待办排队待命。
   - `[-]` **待验收 (Pending Verification)**：交付后静默挂起，Agent 保持绝对静默，严禁自发重复执行与无意义重排查。
   - `[✓]` **已完成 (Done)**：用户确认合格后彻底完结，触发物理即时回收。
   - `[✕]` **不合格 (Rejected)**：用户判定不合格，作为 P0 最高优先级当场重构修复。

3. **零残留任务即时物理回收 (Zero-Lingering Task GC)**
   - 任务验收通过后，**立即从 `flow/plan.md` 物理剪切移入 `flow/archive/`**。
   - 活跃看板零留存已完成任务，从物理层面消除 LLM 注意力被旧任务反复激活的隐患。

4. **任务按需加载机制 (On-Demand Loading)**
   - 开工仅加载当前 1~2 个活动任务切片，静默过滤待验收项，彻底隔离历史归档区。
   - 大幅提升模型上下文信噪比，根除死循环与乱入需求。

5. **双通道执行机制 (Fast Track & Milestone Track)**
   - **快速通道 (Fast Track)**：日常轻量改动、UI 微调、单点 Bug 修复直接改代码并记录精简进展，避免过度流程化。
   - **里程碑通道 (Milestone Track)**：重大功能演进走立项、拆解、执行、评审与回收全套闭环。

6. **配套工程详规**
   - 新增 `references/任务状态机与按需加载SOP.md`
   - 新增 `references/任务回收与归档SOP.md`
   - 升级 `references/工作流程.md`、`references/初始化SOP.md`、`assets/templates/AGENTS.md` 与 `assets/templates/flow/plan.md`。

7. **全双端兼容与别名机制**
   - 原生支持 `project-flow-az` 与 `project-flow-cy` 双别名触发与调用。
   - 完整兼容 Claude Code 与 Codex (`0.145.0+`) 单次续跑 Stop Hook 机制。
## [4.9.0] - 2026-09-20 (四区归档与垃圾分离版)

### Added
- 建立四区归档模型：`history/{plans,tasks,progress}`、`trash/{deprecated,verification}`、`gc/receipts`。
- `flow-gc.py` 增加 GC 回执，验证垃圾和日志轮转均可追溯。
- `sync-project.py` 热更新时自动补齐四区目录，并迁移旧 `history/进展_archive.md` 与 `trash/verification-gc`。
- `audit-flow.py` 增加四区目录规范检查。
- 新增 `tests/test-archive-layout.py`。

### Changed
- 任务归档、日志轮转、验证垃圾、废弃隔离四类语义彻底分离，不再统称“回收”。
- `flow/history/` 只保留已验收或无风险冷数据；`flow/trash/` 只保留明确废弃或验证过程垃圾。

### Verification
- `py_compile`、审计、布局迁移、路由、预算、门禁、交付卡和结构测试全部 Exit 0。
## [4.9.1] - 2026-09-20 (收工看板强制输出版)

### Fixed
- 修复任务完成后只写“flow 状态”摘要、不输出任务看板的问题。
- `flow-deliver.py` 现在同时生成完整四状态任务看板和交付验收卡。
- 项目/全局合同要求收工必须运行 `flow-deliver.py` 并原样粘贴输出，禁止用辅助状态摘要替代看板。

### Verification
- 交付卡测试、路由、预算、门禁、审计、归档布局和结构测试全部 Exit 0。
- 以 `zhengjie-hrm` 真实任务卡演练，输出包含 P1-2 当前待办、P1-1 待验收和完整交付验收卡。
## [4.9.2] - 2026-09-21 (完整收工汇报版)

### Fixed
- 修复收工只输出任务看板和验收卡、丢失原始工作汇报的问题。
- `flow-deliver.py` 新增 `本轮工作汇报`：做了什么、为什么、怎么理解、产出路径、问题解决、下一步。
- 收工合同要求同时粘贴任务看板、工作汇报和交付验收卡，任务看板不能替代工作汇报。

### Verification
- 交付卡测试、路由、预算、门禁、审计、归档布局和结构测试全部 Exit 0。
- 使用真实 P0 任务卡演练，输出完整三段式报告。
