# project-flow 接管控制面（本仓库既是 skill 源，也是被接管的项目）

> 用途：让后续会话能「被接管、被路由、能接手」。此前本仓库没有 `flow/`，
> 任何新会话进去 flow-boot 都报「未接管」→ 无路由/无门禁/无交接协议，只能裸做后中断。

## 🎯 当前聚焦待办 (P0)

- 无（PFP-RELAY-CLARITY-20260924 已交付，等人工验收后归档）

## ⏳ 待人工验收 (Pending Verification)

- [-] PFP-RELAY-CLARITY-20260924 [P0] 等人工验收：撤掉交接棒字节上限 + 接力提示词自包含（工作根绝对路径 + 具体 ticket 路径，实测修复 UUID 被误当 ticket）（v4.15.16）。
- [-] PFP-STOP-RECEIPT-SELFREF-20260924 [P0] 等人工验收：熔断回执自引用不再永久阻塞接手的新会话
  （`read_pending_stop` 用上一条回执快照作对照），负面「熔断后未落新交接棒」仍 fail-closed（v4.15.15）。
- [-] PFP-ORPHAN-RECEIPT-20260923 [P1] 等人工验收：孤儿熔断回执可显式作废，
  `flow-boot.py --void-stale-receipt` 列候选 + `--confirm` 显式作废 + `flow/gc/receipts/` 留痕，
  无参不改行为（v4.15.14，`tests/run-all.sh` 17 项 Exit 0）。
- [-] PFP-RELEASE-20260923 [P0] v4.15.0 → v4.15.13 十四个版本已推送远端，等人工验收：
  交接棒被顶掉仍可核销、核销参照不退回孤儿回执、规格点台账硬门禁、外部心跳、提示词可取回。
  （v4.15.14 已接续推送，远端 HEAD 不再是 b19f005 —— 见 PFP-ORPHAN-RECEIPT-20260923）

## 📦 已完结归档 (Archived in flow/history/)

- 无（本条在验收通过后移入 `flow/history/tasks/`）
