# 决策日志 (decisions)

> 记"过程决策 + 为什么"。**追加,不删改**——下一棒最值钱的上下文。
> (架构 / 产品级的"为什么"按 `flow/规范/文档维护SOP.md` 进 `AGENTS.md`;这里记项目怎么推进的过程决策。)

<!-- 模板:
## YYYY-MM-DD · <决策标题>
- 背景:
- 决定:
- 否决的方案 & 原因:
-->

## 2026-09-23 · WARN 预警回执
- 决策：**先不加**（用户 2026-09-23 明确）。
- 影响：只到 WARN 的会话在下次开工不会被强制；仅靠中段复查 + 外部心跳两道软防线。

## 2026-09-24 · 唯一正式位置
- 决策：project-flow 的**唯一正式 checkout** = `/Users/chinkinoko/projects/project-flow-az`。
- 动作：`~/.codex/skills/project-flow-az` 软链已改指向它（原指向 `~/projects/ai-hardware/project-flow-cy`）。
- 旧路径处置：**不删除、不修改**——它是 ai-hardware 项目根下的子目录，删除会破坏 ai-hardware 结构。
  标注为「已被取代」。**不要再在旧路径改 skill**，否则两份 checkout 会分叉。
- 影响：后续所有会话通过软链使用同一份，不会再开错目录。
