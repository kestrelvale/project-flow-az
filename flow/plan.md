# project-flow 接管控制面（本仓库既是 skill 源，也是被接管的项目）

> 用途：让后续会话能「被接管、被路由、能接手」。此前本仓库没有 `flow/`，
> 任何新会话进去 flow-boot 都报「未接管」→ 无路由/无门禁/无交接协议，只能裸做后中断。

## 🎯 当前聚焦待办 (P0)
- [-] PFP-BOARD-MARKERS-20260926 【用户指派·已交付】严格化 board_visible：锚定 flow-deliver 的分区契约，挡掉空承诺/讨论/引用规则的假阳性。
  缺陷实测：`BOARD_MARKERS=('任务状态看板','当前聚焦待办')` 用 in 判断，5 段非看板文本里 3 段被误判为「已贴看板」
  （含「本轮我确保会输出…」这种空承诺，以及引用规则原文那段——它本身就在 flow-budget 的输出里）。
  写入边界：scripts/flow-budget.py、scripts/flow-deliver.py（导出契约）、tests/test-report-visibility.py。
  验证：`python3 tests/test-report-visibility.py` + `bash tests/run-all.sh`。

- [-] PFP-DELIVERY-PIPE-20260926 【框架修复·已交付】机检不得把「模型草稿」当「对外回复」。
  证据：flow/reports/20260926-总控会话为什么长这样.md；总控 thread 3/3 收工点 last_agent_message 均不含看板，
  且其中 2 个以 <analysis> 开头（最长 33,805 字符的思考草稿）。
  要做的：① last_visible_reply 先剥 <analysis>/<thinking> 再判 board_visible，剥空判「不可判定」而非「没贴」；
            ② 优先用 response_item 里最后一条 role==assistant 作为观测量；③ BOARD_MARKERS 改四分区+顺序校验。
  写入边界：scripts/flow-budget.py、scripts/flow-boot.py、tests/test-report-visibility.py。
  验证：`python3 tests/test-report-visibility.py` + `bash tests/run-all.sh`（23 项 Exit 0）。

- [-] PFP-ACCEPT-4.15.19-20260926 【独立验收·已交付】用 TDD+ATDD 验收 4.15.19 两条打回修复，并排查未执行完的移交物。
  输入：工作区未提交改动（scripts/flow-budget.py、tests/test-relay-multi-task.py、VERSION、CHANGELOG.md）。
  输出：① 篡改断言必须变红、还原后必须变绿（证明测试真能失败）；② 独立 ATDD 断言清单（不复用实现方自己的断言）；③ 全仓未完成项清单。
  写入边界：tests/accept-4.15.19.py（只读复核，不改业务脚本）。
  验证：`python3 tests/test-accept-4.15.19.py` + `bash tests/run-all.sh`（23 项 Exit 0）。

- [-] PFP-RELAY-IDENTITY-20260925 【打回修复·已交付】来源交接棒必须按 ticket 精确定位，不得贴另一张卡的现状/下一步。
  缺陷：`handoff_fields()` 取 `flow/进展.md` 顶部第一条，与 `resolve_ticket()` 解析出的卡可能不是同一张 →
  提示词出现「来源任务卡=B 卡 / 来源交接棒=A 卡 / 当前状态=调度中(A 卡的)」自相矛盾。
  写入边界：`scripts/flow-budget.py`、`tests/test-relay-multi-task.py`。
  验证：`python3 tests/test-relay-multi-task.py` + `bash tests/run-all.sh`。

- [-] PFP-RELAY-MULTITASK-20260924 【打回修复·已交付】显式点名优先于子串匹配，不得被「引用了他卡编号」的条目兜底。
  缺陷：意图点名 B，而活跃区里 A 条目文字含 B 的编号 → 第 471-473 行先命中 A 并 return，永远走不到显式点名保护。
  写入边界：`scripts/flow-budget.py`、`tests/test-relay-multi-task.py`。
  验证：`python3 tests/test-relay-multi-task.py` + `bash tests/run-all.sh`。

## ⏳ 待人工验收 (Pending Verification)


- [-] PFP-REPORT-VISIBILITY-20260925 [P0] 等人工验收： 看板/汇报要么不打印、要么被截断或自相矛盾：（v4.15.17）
  ① flow-deliver 归档分区在 plan 占位「无」而 history 有卡时输出「无」；
  ② 决策分区把多行条目的续行当独立条目输出（半截 `- 决策:`）；
  ③ 漏贴看板无任何机检——新增 board_in_reply，让「上轮回复缺看板」在下一轮开工被点名。
  写入边界：`scripts/flow-deliver.py`、`scripts/flow-budget.py`、`scripts/flow-boot.py`、`tests/test-report-visibility.py`。
  验证：`python3 tests/test-report-visibility.py` + `bash tests/run-all.sh`。

> 4 张卡（PFP-RELEASE / PFP-ORPHAN-RECEIPT / PFP-STOP-RECEIPT-SELFREF / PFP-RELAY-CLARITY）已由用户 2026-09-24 指令验收通过并归档）

## 📦 已完结归档 (Archived in flow/history/)

- PFP-RELEASE-20260923 / PFP-ORPHAN-RECEIPT-20260923 / PFP-STOP-RECEIPT-SELFREF-20260924 / PFP-RELAY-CLARITY-20260924（4 张，证据 `tests/accept-pending-cards.py` 全绿）
