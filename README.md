# project-flow-az

> 基于开源协作框架深度魔改的 **AI 多 Agent 协作与任务闭环管理体系（V4.9.8 完整收工汇报版）**。
> 彻底解决“历史任务死循环复读、缺乏即时回收机制、上下文全量污染、旧计划绑架当面指令、流程管理漂移、ASCII 排版错乱”等工程治理弊端。兼容 `project-flow-az` 与 `project-flow-cy` 双别名触发。

把任何项目（代码 / 调研 / 内容 / 方案）当 repo 管的一套 **企业级 AI 多 Agent 协作流程与闭环状态机**。

## 四阶段与驱动模式（唯一映射）

项目生命周期单向流转，每个阶段绑定一种驱动模式，任务卡 `mode` 与 `method` 必须对齐，由 `flow-gate.py --phase <阶段>` 放行：

| 项目阶段 | 计划模式 | 驱动模式 | 任务卡 `mode` | 阶段职责 |
|---|---|---|---|---|
| 项目初期 | Plan / Goal | SDD | `plan` | 定目标、锁规格、拆原子任务；只读，不改业务代码 |
| 实现期 | - | TDD | `execute` | 先写失败测试，再最小实现使其通过 |
| 验收期 | - | ATDD | `review` | 把验收标准转成可执行断言并留证据 |
| 收尾期 | - | BDD | `handoff` | Given-When-Then 描述行为，交接下一步动作 |

流转顺序固定为 `plan -> execute -> review -> handoff`，不跳阶段、不混用。任务卡以 `goal` 表达目标（旧卡兼容 `objective`）。注意：本流程中的 `plant` 指 Plan（计划模式），不是 PlantUML 等图示工具。

核心是三句话：

- 上下文落进文件，不锁在对话里。
- Agent 之间靠 `flow/` 和 `docs/` 异步接力。
- 每轮收工写进展，下一棒从文件接上。

这个 skill 负责三类核心操作与四大控制机制：

1. **初始化 / 接入项目**：先判断单体项目、单仓多子项目或多独立仓库，再铺好对应层级的 `flow/`、`docs/`、规则入口和方法论副本。project-flow 不安装任何 Hook。
2. **开工接管与路由**：项目内执行型回合首动运行 `flow-boot.py`，完成热同步、审计、任务状态汇总、Plan / Execute / Review / Handoff 路由、预算门禁和回收建议。
3. **任务四状态机闭环与分级回收**：按 `[ ]`待完成、`[-]`待验收、`[✓]`已完成、`[✕]`不合格流转任务；待验收积压会明确暴露，但不能自动验收或自动归档。
4. **收工交付与交接**：验证留有 Exit 0 证据、准备提交人工验收时，才输出完整四状态看板与交付验收卡；交接写入 `flow/进展.md` 顶部。
5. **全局 Skill 自动热同步与版本接管**：项目开工或调用时比对版本并幂等同步规范、合同块与任务卡模板。

**核心防失控与防漂移机制**：
- **用户即时指令第一优先级 (Prompt Priority)**：当前对话诉求 > 历史 plan，严禁被旧计划绑架。
- **极简智能标签看板 (Clean Badge Protocol)**：彻底废止破损的 ASCII 画框，改用高可读性结构化列表，明确标示 `[🤖 自动测试通过]`、`[👤 待人工验收]` 与 `[⚡ 自动决策]`、`[⚠️ 人工决策门]`。
- **任务按需加载与动态销账 (On-Demand Loading & In-Prompt Pruning)**：只读当前 1~2 个活动焦点任务，多要点做完一项即剥离销账，静默过滤待验收项，彻底消除历史上下文污染。
- **高风险人工决策升级门 (High-Risk Bounded Escalation Gate)**：常规开发一律由 Agent 自动决策并记录；仅在极高风险、破坏性变更或用户明确要求时触发人工决策卡。
- **全局 Skill 自动热同步机制 (Auto Hot-Sync)**：全局 Skill 升级后，历史老项目在首次触发时自动无损平滑接管升级，永不脱节。
- **开工状态与收工看板分离**：开工只报当前焦点、路由阻塞、未纳管遗留、待验收计数、待人工决策和回收建议；待验收、归档、本轮决策只在收工阶段输出。
- **会话预算门禁**：读取真实 session token、缓存、轮次和工具调用数据；WARN/STOP 时给出可复制的新会话接力提示词。
- **接管失败显式化**：cwd 不在任何已接入项目内时，入口明确报告“未接管”并返回非零，不再静默成功。
- **四区归档治理**：任务归档、日志轮转、验证垃圾、废弃隔离四类对象分离，所有移动写入 `flow/gc/receipts/` 回执。

它不处理具体业务内容。业务方案、代码、调研、设计稿仍由对应项目和对应 Agent 完成；`project-flow-az` 只负责把协作方式、状态机闭环与交接结构立起来。

## 适用场景

当你需要：

- 给一个新项目搭 Claude Code / Codex 共用的协作骨架与状态机
- 把已有项目接入 `flow/` + `docs/` 文件化流程并实施任务四状态机治理
- 管理同时包含前端、后端、落地页或多个服务的单仓项目
- 让多个 AI 会话、多个终端或多个模型之间能稳定接力，杜绝死循环和任务中断
- 防止会话历史膨胀，实施物理剪切归档 (`history/`) 与废弃隔离 (`trash/`)
- 让老项目随全局 Skill 自动热升级，获得最新状态机与智能看板能力

就用这个 skill。

## 安装

把仓库 clone 到你的 skill 扫描目录。目录位置取决于客户端配置；常见做法：

```bash
# Codex / 本机统一技能目录示例
git clone https://github.com/kestrelvale/project-flow-az ~/.codex/skills/project-flow-az

# 如果你的 Claude Code 扫描 ~/.claude/skills
git clone https://github.com/kestrelvale/project-flow-az ~/.claude/skills/project-flow-az
```

如果你用的是统一的技能仓库，也可以把本仓库作为子目录放进去，例如：

```bash
git clone https://github.com/kestrelvale/project-flow-az ~/Documents/cc-skills/project-flow-az
```

安装或更新后，新开会话，确认 skill 列表里出现 `project-flow-az`（或 `project-flow-cy`）。

> **引擎随仓库分发**：`scripts/` 下的运行时（`flow-boot.py` / `flow-gate.py` / `flow-deliver.py` / `flow-budget.py` / `flow-gc.py` / `audit-flow.py` / `sync-project.py` / `flow-sync.sh`）已纳入版本控制，`git clone` 后即可直接运行，无需额外安装步骤。结构测试会校验这些脚本未被 `.gitignore` 排除。

## WikiSkill：持久经验与技能演化

本仓库同时发布 WikiSkill，用于把 Agent 的执行轨迹编译为可复用的持久知识和技能，避免会话中断后丢失上下文。

### 一键安装、初始化与挂载

在终端执行：

```bash
git clone https://github.com/kestrelvale/project-flow-az.git
cd project-flow-az
bash scripts/install_wikiskill.sh
```

脚本会检查 Python 3.10+，初始化 `raw/traces/`、`wiki/`、`skills/`，并将 WikiSkill 挂载到 Codex 全局目录和当前项目 `.claude/skills/`。

检查状态：

```bash
PYTHONPATH=. python3 -m wikiskill.cli --workspace . status
```

运行技能演化：

```bash
PYTHONPATH=. python3 -m wikiskill.cli --workspace . evolve \
  --train data/train_tasks.json \
  --val data/val_tasks.json \
  --max-iters 5
```

完整说明见 [`skills/wikiskill/README.md`](skills/wikiskill/README.md)。

## 怎么用

### 每轮开工入口

在已接入项目的根目录，每个执行型回合的第一次工具调用运行：

```bash
python3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent "<本轮任务摘要>"
```

开工阶段只生成状态摘要，不生成完整收工看板：

```text
### project-flow 开工状态

## 🎯 当前聚焦待办 (P0)
## 🚧 路由阻塞
## 🧹 未纳管遗留
## 🧾 只读状态计数
- 待验收：N
## ⚠️ 待人工决策
## ♻️ 回收建议
```

如果当前目录不属于任何已接入项目，入口会明确输出“未接管”并返回非零。

### 初始化 / 接入项目

在目标项目目录里直接复制以下任意指令发给 AI：

```text
用 /project-flow(https://github.com/kestrelvale/project-flow-az) 接入协作流程
```
或：
```text
用 project-flow-az(https://github.com/kestrelvale/project-flow-az) 接入协作流程
```
或：
```text
用 project-flow-az 接入协作流程
```
或：
```text
给这个项目搭 flow/docs 协作骨架
```

执行时会先读 `references/初始化SOP.md`。存在多个代码目录时，还会读 `references/多子项目结构.md`，先报告项目边界判断，再列出将创建 / 修改的文件，等你确认后动手。已有项目走非破坏合并：缺什么补什么，不覆盖用户已有内容。

初始化后的典型结构：

```text
项目/
├── AGENTS.md  ←→ CLAUDE.md
├── DESIGN.md                        # 可选，设计 / 创意项目才建
├── flow/
│   ├── charter.md
│   ├── plan.md
│   ├── 进展.md
│   ├── decisions.md
│   ├── 踩坑记录.md
│   ├── tasks/
│   ├── history/                       # 历史完结与日志滚动归档区 (开工不加载)
│   ├── trash/                         # 废弃方案与垃圾物理隔离区 (彻底隔离)
│   └── 规范/
│       └── VERSION                    # 规范版本标记 (用于无感热更新)
├── docs/
├── scripts/、src/ 或现有代码目录     # 保留项目自己的代码布局
└── （无 Hook 配置；需要定时执行时由外部 automation 负责）
```

### 收工看板与标签输出示例

任务完成、验证留有 Exit 0 证据并准备提交人工验收时，才输出完整四状态看板：

````markdown
### 📊 任务状态看板
```markdown
# 任务状态看板

## 🎯 当前聚焦待办 (P0)
- [ ] 微信支付退款与结算单全链路闭环

## ⏳ 待人工验收 (Pending Verification)
- [-] 财务对账报表 Web 端重构 [👤 待人工验收]

## 🤖 自动验收通过 (Auto-Verified)
- [✓] 微信支付分账回调异步断言测试 [🤖 自动测试通过]

## 📦 已完结归档 (Archived in flow/history/)
- [✓] 基础架构迁移、SKU品类池搭建已移入 flow/history/

## 💡 本轮决策记录 (Decisions)
- [⚡ 自动决策] 支付超时时间设为 15 分钟，超时自动释放冻结库存
```

👉 **提请验收卡**:
- 交付产出: `https://example.com/finance/settlement`
- 验收类型: `[👤 待人工验收]`
- 核心要点: 财务对账报表已按新规范重构，请人工审核页面字段展示。
````

### 单仓多子项目

当前端、后端、落地页共同服务同一个总体项目，并共享仓库、目标和发布节奏时，它们属于一个项目边界。默认结构是：

```text
总体项目/
├── AGENTS.md
├── CLAUDE.md -> AGENTS.md
├── flow/                              # 唯一总体控制层
├── docs/                              # 文档统一入口
│   ├── product/
│   ├── architecture/
│   ├── contracts/                    # API、事件、数据模型
│   ├── modules/
│   │   ├── frontend/
│   │   ├── backend/
│   │   └── landing/
│   └── reviews/
├── frontend/
│   ├── AGENTS.md
│   ├── CLAUDE.md -> AGENTS.md
│   └── <源码、测试、构建配置>
├── backend/
│   ├── AGENTS.md
│   ├── CLAUDE.md -> AGENTS.md
│   └── <源码、测试、构建配置>
├── landing/
│   ├── AGENTS.md
│   ├── CLAUDE.md -> AGENTS.md
│   └── <源码、测试、构建配置>
└── （无 Hook 配置）
```

根级 `flow/` 统一管理总体目标、计划、任务、决策、问题和交接；根级 `docs/` 统一管理产品、架构、跨模块契约和需要集中查找的模块说明。子项目目录主要保存源码、测试和构建配置，不重复创建 `flow/` 或完整 `docs/`。

### 收工交接

当你完成一棒，需要交给下一个 Agent / 会话：

```text
写个 handoff
```

或：

```text
交接给下一个 agent
```

skill 会在 `flow/进展.md` 顶部追加一条记录，字段包括：

- 做了什么
- 为什么这么做
- 怎么理解
- 产出路径
- 问题和解决
- 下一步

同一条也会贴回对话，方便你直接复制给别的 Agent。

## 文件职责

| 路径 | 作用 |
|---|---|
| `SKILL.md` | skill 入口，定义触发、四状态机与核心操作 |
| `VERSION` | 全局规范版本号 (当前 v4.9.8) |
| `LICENSE` / `NOTICE` | 开源许可证说明 |
| `references/自动版本接管与无感热更新SOP.md` | 全局 Skill 自动比对与项目平滑热升级规范 |
| `references/任务状态机与按需加载SOP.md` | 任务四状态机、智能标签看板、按需加载与决策升级门 |
| `references/任务回收与归档SOP.md` | 双轨任务回收机制 (自动轮转 vs 人工确认) 与垃圾隔离 |
| `references/初始化SOP.md` | 项目接入流程和自检清单 |
| `references/工作流程.md` | 五段式主循环、接力机制、目录归属 |
| `references/多子项目结构.md` | 单体、monorepo、多独立仓库的边界和目录规则 |
| `references/文档维护SOP.md` | `AGENTS.md` 怎么维护 |
| `references/DESIGN维护SOP.md` | `DESIGN.md` 怎么维护 |
| `references/hook机制.md` | 轻量执行协议：无 Hook 的收工检查与会话接力规则 |
| `references/运行时入口与债务审计.md` | 每轮硬首动、按需加载与遗留问题审计协议 |
| `references/驱动模式与验证策略.md` | 按任务类型按需加载 SDD/TDD/ATDD/BDD/Plan 模式 |
| `references/计划模式交接SOP.md` | 明确何时交给 Codex Plan Mode、如何转回 Execute Mode |
| `references/会话预算与接力SOP.md` | 上下文、轮次和工具调用的预算门禁与新会话接力 |
| `scripts/flow-boot.py` | 开工入口：定位项目、热同步、审计、路由、状态汇总与预算门禁 |
| `scripts/audit-flow.py` | 只读检查四状态机、旧格式计划与遗留任务 |
| `scripts/flow-gc.py` | Verification GC 与日志滚动：验证垃圾进入 `trash/verification/`，过长进展进入 `history/progress/` |
| `scripts/flow-gate.py` | Plan / Execute / Review / Handoff 任务卡阶段门禁 |
| `scripts/flow-budget.py` | 读取真实会话 token、缓存、轮次和工具调用，输出 WARN/STOP 与接力提示词 |
| `scripts/flow-deliver.py` | 生成完整四状态看板、六字段工作汇报与交付验收卡 |
| `assets/templates/` | 注入项目的模板文件 |
| `assets/templates/MODULE_AGENTS.md` | 子项目局部规则入口模板 |
| `evals/evals.json` | 单仓、多独立仓库、非破坏接入与运行时合同行为用例 |
| `tests/test-multi-project-structure.sh` | 校验多子项目规则、模板和评测结构一致性 |
| `visual-guide.html` | 可视化说明页 |

## 方法论要点

- **用户即时指令第一优先级**：当前对话具体指令高于历史旧计划，代码与产出落盘实体文件，绝不允许用旧计划推翻当前指令。
- **四状态闭环流转**：`[ ]` 待完成 (P0) -> `[-]` 待验收 (静默) -> `[✓]` 已完成 (物理归档) / `[✕]` 不合格 (P0 重构)。
- **极简智能标签看板**：废弃 ASCII 画框，统一使用结构化列表，明确标示 `[🤖 自动测试通过]`、`[👤 待人工验收]`、`[⚡ 自动决策]`。
- **按需加载与物理隔离**：只读活跃切片，已完成任务物理移出活跃看板至 `flow/history/`，废弃内容入 `flow/trash/`，防止 LLM 注意力被历史文字带偏。
- **任务回收双机制**：进展日志滚动自动回收（保留最新 3~5 条）；业务交付物必须提请验收，经人工确认后才触发物理归档。
- **高风险人工决策升级门**：常规开发一律由 Agent 自动决策并记入 `decisions.md`；架构破坏/高风险改动触发人工决策卡。
- **全局 Skill 自动热更新**：全局 Skill 升级后，历史老项目在首次触发时自动完成规范热同步。
- **双通道机制**：日常单点改动走快速通道 (Fast Track)，重大功能走五段式主循环。
- **一个项目边界一个控制面**：单仓多子项目只保留一套根级 `flow/` 与 `docs/`，不在子项目机械复制。
- **目录归属**：协调 / 推进项目的内容进根级 `flow/`；需要统一发现的知识和方案进根级 `docs/`；代码进对应子项目。
- **规则分层、文档集中**：根级和子项目可以有各自作用域的 `AGENTS.md`，总体文档仍集中管理；代码邻近文档只作为明确例外保留。
- **进展日志**：`flow/进展.md` 是接力棒，新的记录放最上面，顶部那条就是当前 handoff。
- **运行时合同**：根级 `AGENTS.md` 是两个工具共读的规则入口，`CLAUDE.md` 软链到它。
- **文档不漂移**：`AGENTS.md` 的运行时合同固化首屏看板、四状态机、`plan.md` 同步、验收卡与收工进展；该合同由热同步按标记块更新，不依赖任何 Hook。
- **开工只报状态，收工再报验收**：避免把尚未发生的待验收、归档和决策提前打印成已完成事实。
- **回收必须经人工确认**：框架只提示积压和归档建议，不替用户把 `[-]` 改成 `[✓]`。
- **按需加载可观测**：预算门禁读取真实会话用量，不靠模型主观估计上下文长度。
- **非破坏接入**：已有项目只补缺失内容，遇到冲突先列清单请用户确认。

## 更新旧项目

这个 skill 是幂等的。已经接入过的项目可以重复运行初始化操作，用来刷新 `flow/规范/` 下的方法论副本、维护 `AGENTS.md` 运行时合同块并补齐缺失的 `flow/` 与 `docs/` 目录。

## 边界

- 不替你写业务方案、代码、调研或设计成品。
- 不自动提交或推送 GitHub。
- 不把一个 monorepo 的每个代码目录机械初始化成独立项目。
- 不擅自覆盖已有 `AGENTS.md`、`CLAUDE.md` 或用户 Hook 配置。
- 不擅自修改全局 Codex / Claude 配置。

## 许可

GPL-3.0-or-later。
