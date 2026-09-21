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
