# project-flow-az

> 基于 [CY-CHENYUE/project-flow-cy](https://github.com/CY-CHENYUE/project-flow-cy) 深度魔改的 **AI 多 Agent 协作与任务闭环管理体系（四状态机与即时回收版）**。
> 彻底解决原版“历史任务死循环复读、缺乏即时回收机制、上下文全量污染、旧计划绑架当面指令”等工程治理弊端。兼容 `project-flow-az` 与 `project-flow-cy` 双别名触发。

把任何项目（代码 / 调研 / 内容 / 方案）当 repo 管的一套 **AI 多 Agent 协作流程**。

核心是三句话：

- 上下文落进文件，不锁在对话里。
- Agent 之间靠 `flow/` 和 `docs/` 异步接力。
- 每轮收工写进展，下一棒从文件接上。

这个 skill 负责三类核心操作与两大控制机制：

1. **初始化 / 接入项目**：先判断单体项目、单仓多子项目或多独立仓库，再铺好对应层级的 `flow/`、`docs/`、规则入口、收工自检 hook 和方法论副本。
2. **收工交接**：在 `flow/进展.md` 顶部追加一条交接记录，并把同一条贴回对话。
3. **任务状态机闭环与物理回收**：按 `[ ]`待完成、`[-]`待验收、`[✓]`已完成、`[✕]`不合格流转任务，杜绝历史任务反复重跑；任务合格立即物理剪切归档至 `flow/archive/`。

**两大防失控机制**：
- **用户即时指令第一优先级 (Prompt Priority)**：当前对话诉求 > 历史 plan，严禁被旧计划绑架。
- **任务按需加载 (On-Demand Loading)**：只读当前 1~2 个活动焦点任务，静默过滤待验收项，彻底消除历史上下文污染。

它不处理具体业务内容。业务方案、代码、调研、设计稿仍由对应项目和对应 Agent 完成；`project-flow-cy` 只负责把协作方式和交接结构立起来。

## 适用场景

当你需要：

- 给一个新项目搭 Claude Code / Codex 共用的协作骨架
- 把已有项目接入 `flow/` + `docs/` 文件化流程
- 管理同时包含前端、后端、落地页或多个服务的单仓项目
- 让多个 AI 会话、多个终端或多个模型之间能稳定接力
- 收工时生成一条下一棒能直接复制使用的 handoff
- 把方法论副本随项目保存，避免换会话后丢规则

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

## 怎么用

### 初始化 / 接入项目

在目标项目目录里说：

```text
用 project-flow-az 接入协作流程
```
或：
```text
用 project-flow-cy 接入协作流程
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
│   └── 规范/
├── docs/
├── scripts/、src/ 或现有代码目录     # 保留项目自己的代码布局
└── .hooks/ .claude/ .codex/
```

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
└── .hooks/ .claude/ .codex/          # 只放根级
```

根级 `flow/` 统一管理总体目标、计划、任务、决策、问题和交接；根级 `docs/` 统一管理产品、架构、跨模块契约和需要集中查找的模块说明。子项目目录主要保存源码、测试和构建配置，不重复创建 `flow/` 或完整 `docs/`。

已有的子项目 README、工具生成文档或必须紧贴代码维护的说明不会被搬走，只会在根级 `docs/README.md` 建索引。若某个子项目有独立 Git 仓库、版本、发布或团队边界，才把它当成独立项目，建立自己的完整协作骨架。

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
| `SKILL.md` | skill 入口，定义触发和两类操作 |
| `LICENSE` / `NOTICE` | 开源许可证和版权归属说明 |
| `references/任务状态机与按需加载SOP.md` | 任务四状态机、闭环调度与按需加载机制 |
| `references/任务回收与归档SOP.md` | 即时物理剪切、零留存 GC 与日志轮转规范 |
| `references/初始化SOP.md` | 项目接入流程和自检清单 |
| `references/工作流程.md` | 五段式主循环、接力机制、目录归属 |
| `references/多子项目结构.md` | 单体、monorepo、多独立仓库的边界和目录规则 |
| `references/文档维护SOP.md` | `AGENTS.md` 怎么维护 |
| `references/DESIGN维护SOP.md` | `DESIGN.md` 怎么维护 |
| `references/hook机制.md` | 收工自检 hook 的机制与安装说明 |
| `assets/templates/` | 注入项目的模板文件 |
| `assets/templates/MODULE_AGENTS.md` | 子项目局部规则入口模板 |
| `evals/evals.json` | 单仓、多独立仓库、非破坏接入与旧 Hook 升级行为用例 |
| `tests/test-multi-project-structure.sh` | 校验多子项目规则、模板和评测结构一致性 |
| `tests/test-stop-hook.sh` | 验证双端单次续跑、版本门、稳定回合 ID、异常输入与并发防重 |
| `tests/test-codex-stop-hook-e2e.sh` | 显式运行真实 Codex TUI 的首次／同会话／退出恢复回归 |
| `visual-guide.html` | 可视化说明页 |

## 方法论要点

- **用户即时指令第一优先级**：当前对话具体指令高于历史旧计划，代码与产出落盘实体文件，但绝不允许用旧计划推翻当前指令。
- **四状态闭环流转**：`[ ]` 待完成 (P0) -> `[-]` 待验收 (静默) -> `[✓]` 已完成 (物理归档) / `[✕]` 不合格 (P0 重构)。
- **按需加载与物理隔离**：只读活跃切片，已完成任务物理移出活跃看板，防止 LLM 注意力被历史文字带偏。
- **双通道机制**：日常单点改动走快速通道 (Fast Track)，重大功能走里程碑五段式主循环。
- **一个项目边界一个控制面**：单仓多子项目只保留一套根级 `flow/`、`docs/` 和 hook。
- **目录归属**：协调 / 推进项目的内容进根级 `flow/`；需要统一发现的知识和方案进根级 `docs/`；代码进对应子项目。
- **规则分层、文档集中**：根级和子项目可以有各自作用域的 `AGENTS.md`，总体文档仍集中管理；代码邻近文档只作为明确例外保留。
- **进展日志**：`flow/进展.md` 是接力棒，新的记录放最上面，顶部那条就是当前 handoff。
- **运行时合同**：根级 `AGENTS.md` 是两个工具共读的规则入口，`CLAUDE.md` 软链到它。
- **文档不漂移**：`AGENTS.md` 固化收工约束；Stop hook 在 Claude Code 与版本不低于 `0.145.0` 的 Codex 端，每个用户回合只自动续跑一次。更旧或无法识别的 Codex 安全放行；`0.144.1` 的历史消息 ID 事故和 `0.145.0` 三段回归证据见 `references/hook机制.md`。
- **非破坏接入**：已有项目只补缺失内容，遇到冲突先列清单请用户确认。

## 更新旧项目

这个 skill 是幂等的。已经接入过的项目可以重复运行初始化操作，用来补缺失文件、在确认旧脚本属于 project-flow 后升级根级 Hook，或刷新 `flow/规范/` 下的方法论副本。Codex command handler 没变时不需要因脚本内容更新重新批准；自定义 Hook 仍按冲突处理，不会覆盖。

## 边界

- 不替你写业务方案、代码、调研或设计成品。
- 不自动提交或推送 GitHub。
- 不把一个 monorepo 的每个代码目录机械初始化成独立项目。
- 不擅自覆盖已有 `AGENTS.md`、`CLAUDE.md`、hook 配置或用户文档。
- 不擅自修改全局 Codex / Claude 配置。

## 关注公众号

<div align="center">
  <p>扫码关注公众号，获取更新与交流反馈</p>
  <img src="assets/wechat-qr.jpg" alt="WeChat Official Account QR Code" width="200">
</div>

## 许可

GPL-3.0-or-later。

使用、复制、修改或分发本项目时，请保留 CY-CHENYUE 的版权和许可证声明；如果分发修改版或派生版本，也需要按同一许可证开源。
