# project-flow 接管控制面（本仓库既是 skill 源，也是被接管的项目）

> 用途：让后续会话能「被接管、被路由、能接手」。此前本仓库没有 `flow/`，
> 任何新会话进去 flow-boot 都报「未接管」→ 无路由/无门禁/无交接协议，只能裸做后中断。

## 🎯 当前聚焦待办 (P0)

- [ ] PFP-ORPHAN-RECEIPT-20260923 [P1] 孤儿回执作废：所属会话已消失的熔断回执会永久阻塞项目，
  需提供显式作废命令（`flow-boot.py --void-stale-receipt`），带留痕与二次确认。

## ⏳ 待人工验收 (Pending Verification)

- [-] PFP-RELEASE-20260923 [P0] v4.15.0 → v4.15.13 十四个版本已推送远端，等人工验收：
  交接棒被顶掉仍可核销、核销参照不退回孤儿回执、规格点台账硬门禁、外部心跳、提示词可取回。

## 📦 已完结归档 (Archived in flow/history/)

- 无（本条在验收通过后移入 `flow/history/tasks/`）
