# project-flow 接管控制面（本仓库既是 skill 源，也是被接管的项目）

> 用途：让后续会话能「被接管、被路由、能接手」。此前本仓库没有 `flow/`，
> 任何新会话进去 flow-boot 都报「未接管」→ 无路由/无门禁/无交接协议，只能裸做后中断。

## 🎯 当前聚焦待办 (P0)
- 无

## ⏳ 待人工验收 (Pending Verification)
- 无

> 2026-09-28 归档记录（用户指令「只验收框架」）：
> 4 张卡（PFP-PHASE-GATE-TRUTH / PFP-PENDING-BLACKHOLE / PFP-BOARD-HARDBLOCK /
> PFP-SPEC-ACCUMULATION）已验收归档至 `flow/history/tasks/`；规格点台账并随之移入
> `flow/history/specs/`（4.15.23 新增的随卡归档行为，本仓实测生效）。
> 验收证据：`bash tests/run-all.sh` 28 项 Exit 0；4 张卡回执齐备、门禁 PASS、台账未回收 0。
> 至此 project-flow 框架线收口：`flow/tasks/` 仅剩 `TEMPLATE.md`，活跃区与待验收区均为空。

## 📦 已完结归档 (Archived in flow/history/)

- PFP-RELEASE-20260923 / PFP-ORPHAN-RECEIPT-20260923 / PFP-STOP-RECEIPT-SELFREF-20260924 / PFP-RELAY-CLARITY-20260924（4 张，证据 `tests/accept-pending-cards.py` 全绿）
