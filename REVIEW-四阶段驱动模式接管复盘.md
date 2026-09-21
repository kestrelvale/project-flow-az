# project-flow 四阶段驱动模式接管复盘

日期：2026-09-21 ｜ 版本：v4.9.3 ｜ 范围：仅 project-flow，不涉及任何业务代码

## 1. 用户说的是什么问题

project-flow 原本承诺的模式接管，应当是四阶段与四种驱动模式一一对应：

- 项目初期：`Plan / Goal / SDD` —— 定目标、锁规格、拆原子任务；
- 执行测试：`TDD` —— 先写失败测试，再最小实现；
- 验收过程：`ATDD` —— 把验收标准转成可执行断言；
- 任务结尾：`BDD` —— 用 Given-When-Then 提醒下一步与交接。

用户观察到的现象是：

1. 新建会话不按 project-flow 接管任务，任务看板、待验收、人工决策、任务回收时有时无；
2. SDD / TDD / ATDD / BDD 像"写在文档里"而不是"跑在流程里"；
3. 反复修了很多遍，每次都像没落地。

## 2. 修复前的真实机制

三层结构，职责本来是清楚的：

| 层 | 载体 | 职责 |
|---|---|---|
| 入口层 | `scripts/flow-boot.py` | 定位项目、热同步、审计、回收、输出接管路由与预算门禁 |
| 门禁层 | `scripts/flow-gate.py` | 校验任务卡字段是否满足某个阶段 |
| 收工层 | `scripts/flow-deliver.py` | 输出任务看板、工作汇报、交付验收卡 |

阶段到模式的映射**写在门禁里也是对的**：

```text
plan -> SDD    execute -> TDD    review -> ATDD    handoff -> BDD
```

问题不在映射本身，而在字段契约对不上。

## 3. 为什么会跑飞（根因）

### 根因一：`goal` 与 `objective` 字段撕裂（直接故障）

上一轮为了让阶段语义更完整，把 `flow-gate.py` 的每个阶段必填字段里
同时塞进了 `goal` **和** `objective` 两个字段。

但：

- 任务卡模板 `assets/templates/flow/tasks/TEMPLATE.md` 只有 `objective`；
- `flow-deliver.py`、`flow-boot.py` 只读 `objective`；
- 全部测试、全部已接入项目的历史任务卡，都只有 `objective`。

结果是**每一张现存任务卡都缺 `goal`，门禁一律 FAIL**。
因为 `flow-boot.py` 会把门禁退出码并入自己的退出码，开工入口随之返回非零。
表现出来就是"新会话不接管、看板消失、流程像没跑"——不是逻辑没写，而是
门禁把整条流水线卡死在第一道关。

这解释了用户"改了这么多遍还是没落地"的体感：每改一次字段契约，
就与所有历史任务卡和模板再错位一次。

### 根因二：阶段语义没有出现在运行时输出里（认知故障）

映射只存在于 `flow-gate.py` 的一个字典里。运行时只打印
`Plan 路由 / Execute 路由`，从不说"这是项目初期/实现期/验收期/收尾期该做什么"。
于是即便门禁通过，人和模型都无法从输出确认当前处在哪一阶段、该用哪种模式。

### 根因三：运行时引擎从未纳入版本控制（结构性故障）

`.gitignore` 第 22 行有 `/scripts/`，注释写的是"防止有人在 skill 仓库里
误跑产生的运行时输出"。但 `scripts/` 装的正是引擎本体
（`flow-boot.py` / `flow-gate.py` / `flow-deliver.py` 等，约 1400 行）。

后果：

- README 第 50 行承诺 `git clone` 即可安装，但新克隆里 `scripts/` 只有
  `install_wikiskill.sh`，引擎完全缺失；
- 所有引擎改动都停留在本地工作区，不进 commit、不被备份、无法分发；
- 本机因为 `~/.codex/skills/project-flow-az` 是软链到工作区才一直"能跑"。

这是"修了很多遍却传不出去"的根本原因，建议单独决策处理。

## 4. 本次落地了什么

| 改动 | 文件 | 作用 |
|---|---|---|
| `goal` / `objective` 互为别名，二者至少其一 | `scripts/flow-gate.py` | 新卡用 `goal`，旧卡继续可用，不再一刀切 FAIL |
| 门禁文档串明确四阶段映射 | `scripts/flow-gate.py` | 代码自身说明 `plan->SDD ... handoff->BDD` |
| 任务卡模板补 `goal` 与四阶段产出区 | `assets/templates/flow/tasks/TEMPLATE.md` | 新建任务卡天然符合门禁 |
| 路由输出打印阶段语义 | `scripts/flow-boot.py` | 明确"项目初期/实现阶段/验收阶段/收尾阶段" |
| 收工卡兼容 `goal` | `scripts/flow-deliver.py` | 新卡目标能正确显示 |
| 唯一映射表写进入口 | `SKILL.md`、`references/驱动模式与验证策略.md` | 阶段与模式单一事实来源 |
| 全局合同同步 | `assets/templates/AGENTS.md`、`~/.codex/AGENTS.md`、`~/.claude/CLAUDE.md` | 所有项目开工即按同一映射执行 |
| 回归用例 | `tests/test-flow-gate.py`、`tests/test-flow-boot-routing.py`、`tests/test-multi-project-structure.sh` | 锁死四阶段字段与别名兼容 |

## 5. 验证证据

```text
python3 -m py_compile scripts/*.py                     Exit 0
tests/test-archive-layout.py                           PASS
tests/test-audit-flow.py                               PASS
tests/test-flow-boot-routing.py                        PASS
tests/test-flow-budget.py                              PASS
tests/test-flow-deliver.py                             PASS
tests/test-flow-gate.py                                PASS
tests/test-multi-project-structure.sh                  PASS
git diff --check                                       OK
```

端到端实测（临时项目，非业务仓库）：

- 带 `goal` 的 `plan` 卡：`flow-boot` 接管，输出 `Plan 路由`，门禁 Exit 0；
- 依次改 `mode` 走完 `execute -> review -> handoff`：三道门禁均 Exit 0；
- 故意缺 `verify_command` 的 `execute` 卡：门禁正确 FAIL；
- 只有 `objective` 的旧卡：门禁 Exit 0、接管正常，历史项目不破；
- 版本 4.2.0 的临时项目开工：热同步到 4.9.3，`AGENTS.md` 写入阶段映射。

## 6. 没有达成 / 待决策

1. **引擎未纳入版本控制**：`.gitignore` 的 `/scripts/` 仍未移除，引擎改动
   不会被 commit、备份或分发，新克隆依旧没有引擎。需要用户确认后再动。
2. **Codex 原生 Goal 未接入**：本机没有可靠的原生 Goal 协议证据，
   当前 `goal` 落实为任务卡字段与阶段语义，不代表已接入原生接口。
3. **阶段流转靠门禁约束，不靠自动状态机**：`plan -> execute -> review -> handoff`
   是单向约定 + 门禁校验，尚未做成自动推进的状态机。
4. **未提交、未推送**：本轮改动全部留在本地工作区。
