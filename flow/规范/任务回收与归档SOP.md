# 归档、垃圾回收与日志轮转 SOP

> 解决 Agent 历史包袱过重、上下文注意力被旧任务劫持的根本机制：**任务归档、验证垃圾、日志轮转、废弃隔离四类对象分离，活跃区物理零留存。**

---

## 0. 四区模型与术语

不要把四类不同生命周期的对象统称为“回收”：

| 术语 | 对象 | 目标目录 | 是否代表验收通过 |
|---|---|---|---|
| Task Archive | 已完成计划、已验收任务卡 | `flow/history/plans/`、`flow/history/tasks/` | 是 |
| Log Rotation | 过长进展日志 | `flow/history/progress/` | 否 |
| Verification GC | 验证临时目录、测试输出、探测日志 | `flow/trash/verification/` | 否 |
| Deprecated Trash | 用户明确废弃的方案、任务、草稿 | `flow/trash/deprecated/` | 否 |

```text
flow/
├── history/
│   ├── plans/       已验收计划
│   ├── tasks/       已验收任务卡
│   └── progress/    滚动进展日志
├── trash/
│   ├── deprecated/  用户明确废弃
│   └── verification/ 验证过程垃圾
└── gc/
    └── receipts/    归档与垃圾回收回执
```

`history/` 只表示可追溯的已验收历史；`trash/` 只表示明确废弃或验证过程垃圾。两者禁止混用。

---

## 1. 为什么打勾 `[x]` 留在 plan.md 是“伪回收”？

1. **伪回收的致命危害**:
   - 很多时候开发者误以为把任务改成 `- [x] 某任务` 就是完成了。
   - 但对大模型而言，`[x]` 后面的文本依然会被 Self-Attention 全文阅读！
   - 一旦用户提出新指令或模糊指令，模型看到 `[x]` 里的历史关键词，仍然会被激活并反复重跑旧逻辑。
2. **真回收的物理铁律**:
   - **完成即剪切 (Cut on Done)**: 只要一个任务验收完成，**必须物理删除/剪切出 `flow/plan.md`**，移入 `flow/history/`。
   - `flow/plan.md` 活跃区**物理禁止出现 `[x]`**，只允许有 `[ ]`（进行中/待办）或 `IDLE (等待新任务)`！

---

## 2. 任务回收的双轨分类 (Two Types of Task GC)

为确保回收机制严谨且不破坏业务交付体验，任务回收分为 **自动回收** 与 **人工确认回收** 两类：

```
                              ┌─────────────────────────────┐
                              │     任务回收机制 (Task GC)   │
                              └──────────────┬──────────────┘
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     ▼                                               ▼
         【自动处理：Log Rotation / Verification GC】       【人工确认：Task Archive / Deprecated Trash】
         · 对象: 进展日志 / 临时中间产物                     · 对象: 交付任务 / 废弃方案
         · 去向: history/progress、trash/verification       · 去向: history/plans|tasks、trash/deprecated
         · 零人工干预，保持活跃区轻量                        · 必须先验收或明确废弃后才能移动
```

### 2.1 类型一：自动回收 (Automated GC)
- **适用场景**：
  1. **进展日志滚动轮转 (Log Rotation)**：`flow/进展.md` 活跃区默认**仅保留最新 3~5 条记录**。当新增第 6 条交接记录时，自动将旧记录剪切沉淀至 `flow/history/progress/进展_YYYYMM.md`；
  2. **验证垃圾回收 (Verification GC)**：执行调试、临时测试或探测产生的白名单临时目录，自动移入 `flow/trash/verification/`，严禁残留堆积在根目录。
- **特征**：全自动静默执行，无需用户确认，确保上下文始终轻量。

### 2.2 类型二：人工确认回收 (Human Confirmation GC)
- **适用场景**：
  1. **业务功能与代码重构交付**：任何涉及产品需求、界面、接口或系统逻辑的实质性交付；
  2. **阶段性计划与任务卡 (Tasks)**：`flow/plan.md` 中的活跃待办与 `flow/tasks/` 下的任务卡。
- **铁律约束**：
  - **严禁 Agent 自作主张直接标记已完成并自动销账**！
  - 必须严格遵循流程：`[ ]` 交付 -> 置为 `[-] 待验收` -> 渲染【提请验收卡】-> 用户回复“通过/OK/合格” -> 标记为 `[✓]` -> **立即物理剪切移入 `flow/history/`**。
  - 若用户未确认或指出问题，状态转为 `[✕] 不合格`，当回合立即作为 P0 优先级修复重构。

---

## 3. 两大物理隔离区：历史归档库 vs 废弃垃圾堆

```
                    ┌────────────────────────────────────────┐
                    │       活跃控制区 (Active Pool)         │
                    │ plan.md (≤2项) / 进展.md (最新3~5条)   │
                    └───────────┬────────────────┬───────────┘
                                │                │
                   正常验收通过 │                │ 判定废弃/推翻重做
                   滚动超出限制 │                │ 错误方案作废
                                ▼                ▼
            ┌────────────────────────┐  ┌────────────────────────┐
            │   flow/history/ 归档区  │  │    flow/trash/ 废弃区   │
            │ (供日后追溯，开工不加载)│  │ (彻底隔离，绝不复读)    │
            └────────────────────────┘  └────────────────────────┘
```

### 3.1 历史归档库 (`flow/history/`) —— 已验收冷备份
- **存放内容**：
  - `flow/history/plans/<plan-id>.md`：已完结的阶段性计划；
  - `flow/history/tasks/`：已完成并验收的实体任务卡；
  - `flow/history/progress/进展_YYYYMM.md`：滚动轮转出的历史进展日志。
- **调度准则**：仅供日后复盘追溯。Agent 开工时**默认绝不加载**，彻底切断历史文本对模型注意力的干扰。

### 3.2 隔离区 (`flow/trash/`) —— 明确废弃与验证垃圾
- `flow/trash/deprecated/`：用户明确判定“方向错误、废弃此方案、推翻重构”的无效设计、废弃草稿、废弃任务卡或废弃脚本；
- `flow/trash/verification/`：验证临时目录、测试输出、探测日志等过程垃圾。
- **调度准则**：
  - 废弃方案移动至 `flow/trash/deprecated/` 并打上 `[TRASHED]` 标记；
  - 验证垃圾按时间戳移动至 `flow/trash/verification/`；
  - **绝对隔离**：`flow/trash/` 下的所有文件严禁再次作为需求或待办读入上下文，杜绝“死灰复燃”。

### 3.3 回执 (`flow/gc/receipts/`)

每次任务归档、日志轮转或验证垃圾移动后，必须写入可追溯回执，至少包含：

- 操作类型；
- 源路径与目标路径；
- 原因；
- 验收证据或垃圾来源；
- 时间戳。

### 3.4 任务归档必须用工具执行（不再手写回执）

任务归档只能通过 `flow-gc.py --task-archive` 完成，它会移动任务卡并写出标准 JSON 回执：

```bash
python3 ~/.codex/skills/project-flow-az/scripts/flow-gc.py . \
  --task-archive P0-XX --evidence "verify Exit 0" --apply
```

回执格式：

```json
{
  "operation": "task_archive",
  "ticket_id": "P0-XX",
  "from": "flow/tasks/P0-XX.md",
  "to": "flow/history/tasks/P0-XX.md",
  "reason": "user_accepted",
  "evidence": "verify Exit 0",
  "timestamp": "2026-09-22T11:50:13"
}
```

**没有 `--evidence` 会被拒绝归档。** `audit-flow.py` 会检出 `history/tasks/` 下
没有对应 JSON 回执的归档卡并报警——这样“哪个任务归档了、为什么、什么证据”
三问都能用一条命令答出来，而不是靠翻手写 Markdown 猜。

---

## 4. 防反复执行与防漂移铁律
1. **已归档任务不可逆**: 归档区是冷冻区，禁止 Agent 回头扫描；
2. **用户即时指令最高优先级**: 用户当前 prompt 是第一调度源，直接新建活跃任务并执行，不与历史纠缠；
3. **子要点逐项销账 (In-Prompt Pruning)**: 复杂多要点指令，完成一项即打标销账，后续轮次仅保留未完成切片。
