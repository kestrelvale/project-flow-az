# project-flow 接管控制面（本仓库既是 skill 源，也是被接管的项目）

> 用途：让后续会话能「被接管、被路由、能接手」。此前本仓库没有 `flow/`，
> 任何新会话进去 flow-boot 都报「未接管」→ 无路由/无门禁/无交接协议，只能裸做后中断。

## 🎯 当前聚焦待办 (P0)

- [-] PFP-PHASE-GATE-TRUTH-20260927 【本轮·框架修复·已交付】门禁必须读真实相位，斩断自证循环
  缺陷实测（2026-09-27，本仓真机复现）：`flow-boot.py:1483` 用卡自报的 `mode` 当 `phase`
  传给 `flow-gate.py`，而 `flow-gate.py:252` 又要求 `mode == phase` → **两者恒等，门禁结构上不可能失败**。
  实测后果：6 张卡全部 `mode: execute`，boot 一律打印「门禁通过 [execute]」，而它们的 plan 相位
  （SDD 输入/输出/边界）从未走过、验收也从未被独立复核——**门禁在盖章，不是在守门**。
  要做的：phase 改为从 `flow/plan.md` 的**分区位置**推导（`[ ]`=plan、`[-]`=execute、
  `flow/history/`=review/handoff），不再信任卡内 `mode`；同时补 `execute` 相位必须有
  真实存在的失败测试证据，`review` 相位必须有独立于实现方的断言文件。
  写入边界：`scripts/flow-boot.py`、`scripts/flow-gate.py`、`tests/test-phase-gate-truth.py`、`VERSION`、`CHANGELOG.md`。
  验证：`python3 tests/test-phase-gate-truth.py` + `bash tests/run-all.sh`（全绿）+ 篡改验证必红。

- [-] PFP-PENDING-BLACKHOLE-20260927 【本轮·框架修复·已交付】`[-]` 不得变黑洞
  缺陷实测（2026-09-27）：6 张卡堆在 `[-]`、`[ ]` 为空 → 每轮开工「本轮尚未登记原子任务」→
  只能去改框架；改完又新增 `[-]` 卡 → 下轮活跃区又被占满。**这是「改了几十遍没变化」的机制本身**。
  要做的：boot 对超过阈值未验收的 `[-]` 卡计入 `route_block`（先清账才能开新活）；
  并在开工状态里把「`[ ]` 为空且 `[-]` ≥ N」显式报为阻塞。
  写入边界：`scripts/flow-boot.py`、`tests/test-pending-blackhole.py`、`VERSION`、`CHANGELOG.md`。
  验证：`python3 tests/test-pending-blackhole.py` + `bash tests/run-all.sh`（全绿）+ 篡改验证必红。

- [-] PFP-BOARD-HARDBLOCK-20260927 【本轮·框架修复·已交付】漏贴看板从「提示」升为「硬阻塞」
  缺陷（2026-09-27）：`board_visible()` 已修好（能认出真交付、挡掉空承诺，本仓实测验过），
  但「上轮回复缺看板」仍只在路由里提一句，可被忽略 → 脚本跑了、回执落盘、**回复里 0 次看板**。
  要做的：复用 `board_visible()`，把「上轮缺看板」从提示升级为 `route_block`，
  必须先补看板才能登记新意图；「不可判定」（草稿剥空）仍与「确定没贴」分开报。
  写入边界：`scripts/flow-boot.py`、`tests/test-report-visibility.py`、`VERSION`、`CHANGELOG.md`。
  验证：`python3 tests/test-report-visibility.py` + `bash tests/run-all.sh`（全绿）+ 篡改验证必红。

## ⏳ 待人工验收 (Pending Verification)
- [-] PFP-SPEC-ACCUMULATION-20260928 【框架修复·已交付】规格点不再跨任务累积：按卡加载 + 随卡归档 + 首屏只显示本卡

> 2026-09-27 归档记录（用户指令「帮我完成 A」）：
> 5 张卡（PFP-BOARD-MARKERS / PFP-DELIVERY-PIPE / PFP-RELAY-IDENTITY /
> PFP-RELAY-MULTITASK / PFP-REPORT-VISIBILITY）已验收归档至 `flow/history/tasks/`。
> `PFP-ACCEPT-4.15.19-20260926` 判定为**幽灵条目**：`plan.md` 有它，但磁盘上
> **无任务卡、无 specs 台账、无 delivery 回执**（`flow/tasks/` 与 `flow/specs/` 均查无此文件）；
> 其声称的产出 `tests/test-accept-4.15.19.py` 确实存在且实跑 PASS，故本条按「卡本身缺失」如实记录，
> 不从 `plan.md` 静默抹掉——这是「查无回执 1」的真实来源。
> 更早 4 张卡（PFP-RELEASE / PFP-ORPHAN-RECEIPT / PFP-STOP-RECEIPT-SELFREF / PFP-RELAY-CLARITY）
> 已由用户 2026-09-24 指令验收通过并归档。

## 📦 已完结归档 (Archived in flow/history/)

- PFP-RELEASE-20260923 / PFP-ORPHAN-RECEIPT-20260923 / PFP-STOP-RECEIPT-SELFREF-20260924 / PFP-RELAY-CLARITY-20260924（4 张，证据 `tests/accept-pending-cards.py` 全绿）
