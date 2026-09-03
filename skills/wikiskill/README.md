# WikiSkill: 基于持久知识编译的 Agent 经验沉淀与技能演化框架

[![arXiv](https://img.shields.io/badge/arXiv-2608.27454-b31b1b.svg)](https://arxiv.org/abs/2608.27454)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

> **论文官方出处**：Google Research & Virginia Tech (2026)
> **论文题目**：《WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution》
> **核心论文链接**：[arXiv:2608.27454](https://arxiv.org/abs/2608.27454) | [HTML 论文预览](https://arxiv.org/html/2608.27454v1)

---

## 📖 目录 (Table of Contents)

1. [背景与痛点：为什么需要 WikiSkill？](#1-背景与痛点为什么需要-wikiskill)
2. [WikiSkill 核心理念与架构](#2-wikiskill-核心理念与架构)
   - [2.1 三层解耦存储模型 (Three-Tier Storage Model)](#21-三层解耦存储模型-three-tier-storage-model)
   - [2.2 四智能体协同演化机制 (Four Cooperating Agents)](#22-四智能体协同演化机制-four-cooperating-agents)
3. [定量评测与性能提升 (权威论文数据)](#3-定量评测与性能提升-权威论文数据)
   - [3.1 跨模型多基准评测提升 (Table 1)](#31-跨模型多基准评测提升-table-1)
   - [3.2 消融实验：Wiki 层的必要性与隔离原则 (Table 3)](#32-消融实验wiki-层的必要性与隔离原则-table-3)
   - [3.3 复杂度与 API 成本优势 (Table 7)](#33-复杂度与-api-成本优势-table-7)
4. [安装与环境配置](#4-安装与环境配置)
5. [Agent Skill 挂载与部署](#5-agent-skill-挂载与部署)
   - [5.1 在 Codex (OpenAI) 中部署](#51-在-codex-openai-中部署)
   - [5.2 在 Claude Code (Anthropic) 中部署](#52-在-claude-code-anthropic-中部署)
6. [命令行使用指南 (CLI Guide)](#6-命令行使用指南-cli-guide)
7. [Python SDK 深度集成](#7-python-sdk-深度集成)
8. [实战案例：在法律维权项目中的全案落地](#8-实战案例在法律维权项目中的全案落地)
9. [与其他范式的对比 (Reflexion / SkillOpt / Voyager)](#9-与其他范式的对比-reflexion--skillopt--voyager)

---

## 1. 背景与痛点：为什么需要 WikiSkill？

在以大语言模型 (LLM) 为核心的智能体 (Agent) 系统中，让智能体具备“从实践中学习”并“终身持续演化”的能力是实现通用人工智能 (AGI) 的关键。然而，现有的反思与经验沉淀范式存在重大缺陷：

### 现有范式的致命痛点
1. **短上下文内的经验丢失 (Catastrophic Forgetting)**：
   - 如 **Reflexion** 或 **Self-Refine**，反思经验往往作为会话上下文或短期记忆存储，一旦跨越新任务或上下文被截断，先前积累的纠错与探索经验彻底丢失。
2. **经验与技能强耦合引发上下文膨胀 (Context Bloat)**：
   - 现有系统常直接将庞杂的历史执行过程、调试日志直接拼接到任务提示词中。不仅消耗海量 Token，而且严重干扰 Agent 的当前注意力，导致“信息过载反噬推理表现”。
3. **技能库演化缺乏门控机制导致负向退化 (Negative Transfer & Skill Drift)**：
   - 自动生成技能时（如早期 Voyager/EvoSkill），缺少严格的多样本全量验证门控。新技能可能修复了 Task A，却导致 Task B 和 Task C 性能大幅倒退。
4. **单步优化的高昂 API 成本**：
   - 许多技能优化方法在每一步错误发生时即调用重型 LLM 优化器重写技能，开销极大，难以在实际工程中规模化部署。

### WikiSkill 的破局方案
WikiSkill 提出了 **“编译智能体经验至持久知识库”** 的全新范式：
- 借鉴软件工程中 **“编译器”** 的思想：将低级、瞬态、具体的执行轨迹（源代码），提炼编译为抽象、泛化、跨任务通用的维基模式库（中间表示 IR），再按需合成为高内聚、高复用的条件执行技能（目标可执行代码）。
- 引入 **持久单调增长的 Wiki 层** 与 **严格的门控回滚演化闭环**，彻底实现知识零遗忘与技能稳步演进。

---

## 2. WikiSkill 核心理念与架构

WikiSkill 由两大核心机制构成：**三层解耦存储模型** 与 **四智能体协同闭环**。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       WikiSkill 核心工作流总览                          │
└─────────────────────────────────────────────────────────────────────────┘

   [用户任务输入] ──► [Inference Agent] ◄── [条件技能库 skills/] (高精步骤)
                             │                               ▲
                      执行轨迹 (x, y, τ)                      │
                             ▼                               │  门控验收
                    [不可变轨迹 raw/traces/]                  │  通过部署
                             │                               │
                      批量读取 (Batch B)                      │
                             ▼                               │
                     [Wiki Maintainer]                       │
                             │ 提炼通用经验                   │
                             ▼                               │
                    [持久维基层 wiki/] ──► [Skill Proposer] ──┘
                    (模式库/索引/变更日志)    (提出 ADD/UPDATE/REMOVE 提案)
                                                     │
                                                     ▼
                                            [Gating Controller]
                                            (验证集评测/防倒退)
```

### 2.1 三层解耦存储模型 (Three-Tier Storage Model)

| 存储层级 | 物理路径 | 数据特性 | 核心作用 |
| :--- | :--- | :--- | :--- |
| **原始轨迹层 (Raw Traces)** | `raw/traces/` | 只追加、不可变 (Append-only & Immutable) | 忠实记录每一次任务输入的执行轨迹 $(x, y, \tau)$，包含工具调用、环境反馈与最终输出，作为真理来源与离线审计底稿。 |
| **持久维基层 (Persistent Wiki)** | `wiki/` | 单调累加、非破坏性 (Monotonically Growing) | 存放跨任务的通用抽象模式 (`patterns/`)、维基索引 (`index.md`)、变更日志 (`log.md`) 与技能历史影响 (`skill-impact.md`)。 |
| **条件技能层 (Active Skills)** | `skills/` | 条件-行动双文件、动态演化 (Procedural & Evolving) | 存放立即可执行的标准化技能。采用 **双文件架构**：`SKILL.md` (步骤指令) + `PURPOSE.md` (溯源与演化记录)。 |

#### 双文件技能规范 (Dual-File Skill Structure)
每个在 `skills/` 下的技能包包含且仅包含两个核心文件：
1. `SKILL.md`：
   - **YAML Frontmatter**：元数据，遵循标准 Agent Skill 规范。
   - **When to Apply / When NOT to Apply**：明确触发边界与排除场景，防止技能滥用。
   - **Step-by-Step Instructions**：逻辑清晰、可直接执行的操作步骤规范。
2. `PURPOSE.md`：
   - **Origin Traces**：追溯该技能是由哪些具体的原始轨迹提炼而来。
   - **Patterns Addressed**：声明该技能解决了维基中的哪些经验模式或失败陷阱。
   - **Evolution History**：详细记录技能的版本迭代履历。

---

### 2.2 四智能体协同演化机制 (Four Cooperating Agents)

WikiSkill 在演化闭环中明确解耦了四种角色，各司其职：

1. **推理智能体 (Inference Agent, $M_{\text{inf}}$)**：
   - **职责**：面对具体的业务任务，加载当前匹配的活跃技能，调用环境工具完成任务执行，输出最终结果。
   - **核心纪律 (关键设计)**：**严格隔离读取冗长 Wiki 层**。推理智能体只读针对性的 `SKILL.md`，彻底避免上下文过载与无关干扰。
2. **维基维护智能体 (Wiki Maintainer, $M_{\text{wiki}}$)**：
   - **职责**：作为异步的经验分析师，按批次摄入执行轨迹。
   - **工作内容**：识别重复出现的失败原因（Failure Modes）、成功策略（Success Principles）与通用领域规律，以规范化 Markdown 形式写入 `wiki/patterns/`，并同步更新全局索引。
3. **技能提议智能体 (Skill Proposer, $M_{\text{prop}}$)**：
   - **职责**：阅读维基模式库中的最新总结以及尚未解决的失败痛点，生成具体的技能原子操作提案：
     - `ADD_SKILL`：发现全新场景模式，创建新技能。
     - `UPDATE_SKILL`：发现现有技能存在遗漏或缺陷，更新指令与边界。
     - `REMOVE_SKILL`：技能已被更优方案替代或证明无效时退役下线。
4. **门控评测控制器 (Gating Controller, $M_{\text{gate}}$)**：
   - **职责**：演化防火墙。在验证集 $D_{\text{val}}$ 上对比当前技能与提议技能的表现：
     - 若通过格式校验且验证集得分提升（或满足帕累托非退化），批准合并提案。
     - 若性能下降或格式损坏，**原子级回滚** 技能库变更，但保留本次失败归因于维基中，防止重蹈覆辙。

---

## 3. 定量评测与性能提升 (权威论文数据)

论文在三大极具挑战性的 Agent 真实评测基准上进行了端到端对比：
- **ALFWorld**：复杂多步交互式具身具象环境。
- **SpreadSheet**：包含复杂公式、格式与数据变换的电子表格自动化操作。
- **LiveMath**：多步数学与逻辑符号推理竞赛基准。

### 3.1 跨模型多基准评测提升 (Table 1)

WikiSkill 在不同体量、不同架构的模型上均展现出绝对领先的性能增益：

| 评估模型 (Backbone Model) | 零技能基线 (No Skill) | 传统提示演化 (EvoSkill) | 梯度/反射优化 (SkillOpt) | **WikiSkill (本文方案)** | 相对基线净提升 ($\Delta$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Qwen-3.5-4B** (轻量端侧模型) | 26.2% | 31.4% | 33.1% | **38.5%** | **+12.3%** |
| **Qwen-3.5-9B** (中端模型) | 29.9% | 38.6% | 40.2% | **47.4%** | **+17.5%** *(已超越 27B 零技能基线)* |
| **Qwen-3.6-27B** (强力大模型) | 39.4% | 51.2% | 54.8% | **63.3%** | **+23.9%** *(ALFWorld 77.6%, Sheet 81.7%)* |
| **Gemma-31B** | 41.8% | 53.0% | 56.1% | **64.5%** | **+22.7%** |
| **Gemini-3.5-Flash** (商业前沿) | 49.5% | 58.7% | 61.2% | **68.1%** | **+18.6%** *(LiveMath 33.0% 飙升至 72.6%)* |

> 📌 **核心洞见**：在中轻量模型（如 9B）上挂载 WikiSkill 后，其实际任务成功率（47.4%）**显著超越了未挂载技能的 27B 大模型（39.4%）**，实现了小模型通过知识沉淀完成“越级反超”。

---

### 3.2 消融实验：Wiki 层的必要性与隔离原则 (Table 3)

论文的消融实验（Ablation Study）给出了两项极具工程指导意义的结论：

| 配置方案 (Configuration) | 综合得分 (Overall Score) | 核心发现与机制解释 |
| :--- | :---: | :--- |
| **WikiSkill 完整版 (Full Framework)** | **63.7%** | 三层解耦 + 门控演化达到最佳状态。 |
| **移除 Wiki 层 (w/o Wiki Layer)** | **48.7%** | **性能暴跌 15.0%**！证明单纯直接生成技能容易出现经验断层与负迁移。 |
| **移除门控机制 (w/o Gating Controller)** | **53.2%** | **性能下降 10.5%**！出现严重技能退化（Skill Regression）。 |
| **允许推理 Agent 直接读 Wiki (Inference w/ Wiki)** | **60.9%** | **性能反向下降 2.8%**！证明了冗长的背景模式会造成注意力涣散，推理期必须保持技能精简隔离。 |

---

### 3.3 复杂度与 API 成本优势 (Table 7)

传统反射方法在遇到错误时频繁单步触发重型优化器，而 WikiSkill 采用批处理维护与按需提议：

- **传统逐步反射优化复杂度**：$C_{\text{StepWise}} = O(N_{\text{train}} \cdot T_{\text{ReAct}})$
- **WikiSkill 批量编译优化复杂度**：$C_{\text{WikiSkill}} = (1 + T_{\text{ReAct}})\frac{N_{\text{train}}}{B} = O\left(\frac{N_{\text{train}}}{B}\right)$

其中 $B$ 为批次大小（Batch Size）。实验表明，在获得大幅胜率提升的同时，WikiSkill 将优化器调用频率降低了 **60% ~ 80%**，极大节约了 API Token 成本。

---

## 4. 安装与环境配置

WikiSkill 采用现代纯 Python 设计，依赖极简，开箱即用。

### 4.1 环境依赖
- **Python**：>= 3.10
- **运行时依赖**：无第三方依赖（Python 标准库）
- **测试依赖**：`pytest`（仅运行测试时需要）
- **可选依赖**：`graphify`、`codegraph`（若需要构建代码与语义全景图谱）

### 4.2 从线上代码仓库安装

本 WikiSkill 已随 [project-flow-az](https://github.com/kestrelvale/project-flow-az) 发布。直接执行：

```bash
git clone https://github.com/kestrelvale/project-flow-az.git
cd project-flow-az
bash scripts/install_wikiskill.sh
```

仓库内的 `scripts/install_wikiskill.sh` 会一次完成 Python 版本检查、项目初始化、Codex 全局技能挂载、Claude Code 当前项目挂载和状态检查。它不会覆盖已有的同名目录或软链接；目标不属于当前仓库时会直接报错。

如果仓库已经在本地：

```bash
cd <仓库根目录>
bash scripts/install_wikiskill.sh
```

### 4.3 手动安装与测试

```bash
# 1. 检查 Python 版本
python3 --version  # 需 >= 3.10

# 2. 安装测试依赖（运行时不需要第三方包）
pip install pytest

# 3. 验证单元测试通过 (内置存储管理与编排器测试)
PYTHONPATH=. python3 -m pytest wikiskill/tests
```

测试输出示例：
```
============================== test session starts ==============================
collected 5 items
wikiskill/tests/test_orchestrator.py ..                                  [ 40%]
wikiskill/tests/test_storage.py ...                                      [100%]
============================== 5 passed in 0.07s ===============================
```

---

## 5. Agent Skill 挂载与部署

本仓库已将 WikiSkill 自身封装为标准 Agent Skill（存放在 `skills/wikiskill/`），可无缝接入支持 Agent Skills 标准的主流平台。

### 5.1 在 Codex (OpenAI) 中部署

Codex 运行时会主动扫描 `~/.codex/skills/` 目录。推荐从仓库根目录执行一键脚本：

```bash
bash scripts/install_wikiskill.sh
```

验证挂载：

```bash
readlink "$HOME/.codex/skills/wikiskill"
PYTHONPATH=. python3 -m wikiskill.cli --workspace . status
```

### 5.2 在 Claude Code (Anthropic) 中部署

Claude Code 会自动读取当前项目的 `.claude/skills/`。上述脚本会将同一份仓库文件挂载到 `<仓库根目录>/.claude/skills/wikiskill`：

```bash
bash scripts/install_wikiskill.sh
```

挂载完成后，Codex 或 Claude Code 在接收到经验沉淀、技能演化、自适应反思等相关任务时，将自动激活并遵循 `wikiskill` 技能指引。

---

## 6. 初始化、使用与自动化

### 6.1 怎么初始化

一键安装脚本已自动初始化；也可以单独执行：

```bash
cd <仓库根目录>
PYTHONPATH=. python3 -m wikiskill.cli --workspace . init
```

它会创建 `raw/traces/`、`wiki/` 和 `skills/` 三层工作区，已有资料不会被删除。

### 6.2 怎么使用和演化

```bash
PYTHONPATH=. python3 -m wikiskill.cli --workspace . status
PYTHONPATH=. python3 -m wikiskill.cli --workspace . evolve \
  --train data/train_tasks.json \
  --val data/val_tasks.json \
  --max-iters 5
```

`status` 是只读检查；`evolve` 需要训练集和验证集，会运行维护、提议与门控流程。没有数据集时，可使用 `WorkspaceManager.save_trace()` 写入轨迹后再编译。

### 6.3 怎么自动化挂载和更新

“自动化挂载”是一次安装、持续生效：Codex/Claude Code 每次启动都从软链接发现同一份 `skills/wikiskill/`。代码仓库更新后，在仓库根目录重新运行 `bash scripts/install_wikiskill.sh` 即可幂等地重新初始化并检查挂载。

本项目的 Stop Hook 只负责收工检查和 `flow/进展.md` 交接记录，不会把未经确认的草稿自动写入永久知识库；知识演化仍需显式运行 `evolve`，避免敏感材料或无效尝试进入 `wiki/`。

## 7. 命令行使用指南 (CLI Guide)

WikiSkill 提供了简洁直观的 CLI 接口：

### 7.1 查看当前系统资产状态 (`status`)
检查不可变轨迹、持久模式与当前激活的技能：
```bash
PYTHONPATH=. python3 -m wikiskill.cli --workspace . status
```
输出示例：
```
=== WikiSkill Workspace Status [<仓库根目录>] ===
📦 Raw Traces:       6 items
🧠 Wiki Patterns:    6 patterns
⚡ Active Skills:    7 skills

Active Skills:
  - legal_evidence_matrix_construction
  - legal_statutory_authority_verification
  - legal_cross_province_transfer_counter
  - legal_forced_resignation_dispatch
  - legal_dormitory_eviction_defense
  - legal_oral_layoff_counteraction
  - legal_arbitration_application_filing

Wiki Patterns:
  - pattern_evidence_chain_notarization.md
  - pattern_dormitory_eviction_defense.md
  - pattern_oral_layoff_counteraction.md
  - pattern_hostile_cross_province_transfer.md
  - pattern_forced_resignation_dispatch.md
  - pattern_statutory_claim_calculation.md
```

### 7.2 初始化三层工作区 (`init`)
在任何新项目中一键创建三层目录与规范模板：
```bash
PYTHONPATH=. python3 -m wikiskill.cli --workspace . init
```
生成目录结构：
```
├── raw/traces/        # 存放只追加执行轨迹
├── wiki/              # 存放 patterns/、index.md、log.md、skill-impact.md
└── skills/            # 存放可执行的条件技能包
```

### 7.3 运行全自动演化闭环 (`evolve`)
在训练集和验证集上执行 Algorithm 1 自动演化：
```bash
PYTHONPATH=. python3 -m wikiskill.cli --workspace . evolve \
  --train data/train_tasks.json \
  --val data/val_tasks.json \
  --max-iters 5 \
  --early-stop 0.95
```

---

## 7. Python SDK 深度集成

可以在任何自定义 Agent 架构中将 WikiSkill 作为模块引入：

```python
from wikiskill import (
    WorkspaceManager,
    WikiMaintainer,
    SkillProposer,
    GatingController,
    WikiSkillOrchestrator,
    OrchestratorConfig
)

# 1. 绑定工作区
workspace = WorkspaceManager("/path/to/project")
workspace.init_workspace()

# 2. 自定义演化配置
config = OrchestratorConfig(
    max_iterations=5,
    early_stop_score=0.98,
    verbose=True
)

# 3. 启动编排器
orchestrator = WikiSkillOrchestrator(workspace=workspace, config=config)

# 4. 执行多轮演化
summary = orchestrator.evolve(
    train_tasks=[{"task_id": "T01", "instruction": "..."}],
    val_tasks=[{"task_id": "V01", "instruction": "..."}]
)

print(f"演化完成！初始得分: {summary.initial_score} -> 最终最优得分: {summary.best_score}")
print(f"采纳提案: {summary.accepted_proposals} 个，拒绝提案: {summary.rejected_proposals} 个")
```

---

## 8. 实战案例：在法律维权项目中的全案落地

在本项目（深圳高新企业劳动维权实战案）中，WikiSkill 成功将全案 14 份非结构化文书、对抗记录与合同审查报告，完整编译为高可靠的知识底座：

```
                              全案实战编译成效
                                     │
      ┌──────────────────────────────┼──────────────────────────────┐
      ▼                              ▼                              ▼
 [6 条原始不可变轨迹]            [6 大持久维基模式]             [7 个标准化执行技能]
 (raw/traces/)                   (wiki/patterns/)               (skills/)
 • 证据保全与时间戳固化         • 证据链公证与时间戳固化法则     • 诉讼证据矩阵构建技能
 • 组织架构与法定用工排查       • 宿舍恶意断电催迁抗辩规程       • 法定用工主体穿透审查
 • 口头N+1交接对抗规程          • 口头逼退反制与不脱岗抗辩       • 恶意跨省调令复函技能
 • 跨省恶意调令反击函编制       • 恶意跨省调令对抗三步法         • 被迫解除劳动合同送达
 • 被迫解除函邮政寄送证据       • 被迫解除通知函送达规范         • 宿舍断电催迁防御技能
 • 仲裁申请书综合求偿编制       • 仲裁法定求偿精准计算模型       • 口头辞退对抗交涉技能
                                                                • 劳动仲裁申请书编制
```

配合 **CodeGraph**（精准语法树检索）与 **Graphify**（48 实体 / 93 边全景知识图谱），本项目构建起了：
- **底层**：CodeGraph（代码级精准跳转）
- **中层**：Graphify（主体-事实-法条关联推理图谱）
- **高层**：WikiSkill（跨案情经验沉淀、模式总结与自适应技能演化）
的三位一体现代 Agent 认知与执行闭环。

---

## 9. 与其他范式的对比 (Reflexion / SkillOpt / Voyager)

| 核心维度 | Reflexion (2023) | Voyager (2023) | SkillOpt (2024) | **WikiSkill (2026)** |
| :--- | :--- | :--- | :--- | :--- |
| **知识存储载体** | 易失的会话上下文 | 仅有代码技能文件 | 参数优化与技能描述 | **三层解耦 (轨迹-维基-技能)** |
| **抗遗忘能力** | 极弱 (窗口截断即遗忘) | 较弱 (代码更新易冲掉旧逻辑) | 中等 (依赖密集检索) | **极强 (维基单调递增，永久留存)** |
| **失败经验处理** | 任务结束后丢失 | 仅当次尝试被覆写 | 隐式梯度/打分 | **显式沉淀为 Failure Mode 模式** |
| **技能门控机制** | 无门控 | 简单环境单元测试 | 局部评估 | **全量验证集多指标防退化门控** |
| **推理期上下文开销** | 极大 (累积所有反思) | 中等 | 中等 | **最小 (推理端严格隔离维基背景)** |
| **优化器调用成本** | 单步高频 ($O(N)$) | 单步高频 ($O(N)$) | 单步高频 ($O(N)$) | **批量低频 ($O(N/B)$)，节省60%+** |

---

## 📄 引用与致谢 (Citation & References)

如果您在研究或工程项目中使用了 WikiSkill，请引用原作者论文：

```bibtex
@article{wikiskill2026,
  title   = {WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution},
  author  = {Google Research and Virginia Tech},
  journal = {arXiv preprint arXiv:2608.27454},
  year    = {2026}
}
```

---
*Developed with rigor and engineering excellence.*
