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
