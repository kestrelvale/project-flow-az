# project-flow 接管控制面（本仓库既是 skill 源，也是被接管的项目）

> 用途：让后续会话能「被接管、被路由、能接手」。此前本仓库没有 `flow/`，
> 任何新会话进去 flow-boot 都报「未接管」→ 无路由/无门禁/无交接协议，只能裸做后中断。

## 🎯 当前聚焦待办 (P0)

- 无（本轮无活跃卡；两张卡已交付，见下方待验收区）

## ⏳ 待人工验收 (Pending Verification)

- [-] PFP-REPORT-VISIBILITY-20260925 [P0] 等人工验收： 看板/汇报要么不打印、要么被截断或自相矛盾：（v4.15.17）
  ① flow-deliver 归档分区在 plan 占位「无」而 history 有卡时输出「无」；
  ② 决策分区把多行条目的续行当独立条目输出（半截 `- 决策:`）；
  ③ 漏贴看板无任何机检——新增 board_in_reply，让「上轮回复缺看板」在下一轮开工被点名。
  写入边界：`scripts/flow-deliver.py`、`scripts/flow-budget.py`、`scripts/flow-boot.py`、`tests/test-report-visibility.py`。
  验证：`python3 tests/test-report-visibility.py` + `bash tests/run-all.sh`。
- [-] PFP-RELAY-MULTITASK-20260924 [P0] 等人工验收： 接力提示词在多任务并行/多工作区下会指名错卡：（v4.15.17）
  ① 显式交接身份（--ticket/--work-root，写进回执，不再从交接棒标题猜）；
  ② 卡存在性校验（已归档/不存在 → 回退活跃区候选，不给出死路径）；
  ③ 提示词附并行队列与阻塞项快照，并声明分端 worktree 与主仓合并的分工。
  写入边界：`scripts/flow-budget.py`、`tests/test-relay-multi-task.py`。
  验证：`python3 tests/test-relay-multi-task.py` + `bash tests/run-all.sh`。

> 4 张卡（PFP-RELEASE / PFP-ORPHAN-RECEIPT / PFP-STOP-RECEIPT-SELFREF / PFP-RELAY-CLARITY）已由用户 2026-09-24 指令验收通过并归档）

## 📦 已完结归档 (Archived in flow/history/)

- PFP-RELEASE-20260923 / PFP-ORPHAN-RECEIPT-20260923 / PFP-STOP-RECEIPT-SELFREF-20260924 / PFP-RELAY-CLARITY-20260924（4 张，证据 `tests/accept-pending-cards.py` 全绿）
