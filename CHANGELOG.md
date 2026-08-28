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
