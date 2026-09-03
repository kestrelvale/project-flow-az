# Purpose & Evolution: wikiskill

## Origin
提炼自论文《WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution》（arXiv:2608.27454，Google Research & Virginia Tech, 2026）以及全工程实战落地。

## Patterns Addressed
- `pattern_agent_catastrophic_forgetting`: 传统提示词反思中的经验遗忘与负向迁移。
- `pattern_trace_skill_coupling`: 原始执行轨迹与可执行技能强耦合导致的上下文膨胀。
- `pattern_unregulated_skill_drift`: 缺乏门控检验机制导致技能库质量退化。

## Evolution History
- v1.0.0 (2026-09-02): 首次工程化打包为标准 Agent Skill，确立了三层解耦存储、四智能体协同闭环、CLI 运维工具与全自动门控演化规范。
