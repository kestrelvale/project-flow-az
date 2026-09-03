---
name: wikiskill
description: "Use when an agent needs to accumulate task execution experience into persistent knowledge, avoid catastrophic forgetting, compile traces into abstract pattern wikis, or propose, test, and gate-evolve procedural skills according to arXiv:2608.27454 (WikiSkill). Suitable for creating skills, evolving existing skill libraries, or inspecting execution patterns."
---

# WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution

WikiSkill is an agent self-evolution and lifelong skill learning framework based on arXiv:2608.27454 (Google Research & Virginia Tech, 2026). It decouples ephemeral trajectories from actionable skills by introducing a persistent, monotonically accumulating Wiki layer.

## When to Apply
- The agent has accumulated execution traces or task outcomes and needs to synthesize them into reusable, structured patterns.
- The user requests skill generation, skill refinement, bug-fixing in skill libraries, or lifelong learning for an agent system.
- Preventing catastrophic forgetting: when new skills are proposed, an automated gating mechanism must ensure no performance regression occurs across historical benchmarks.
- Workspace initialization: setting up the three-tier storage architecture (`raw/traces/`, `wiki/`, `skills/`) for an intelligent project.

## When NOT to Apply
- Direct, one-shot script execution or trivial single-file edits that require no abstraction or reusable skill accumulation.
- Real-time online streaming inference where execution latency cannot tolerate asynchronous wiki synthesis or multi-agent proposal cycles.

## Core Architecture & Workflow

### 1. Three-Tier Storage Model
1. **Raw Trajectory Layer (`raw/traces/`)**:
   - Append-only, immutable record of historical task execution traces $(x, y, \tau)$.
   - Serves as the immutable ground truth for audit, debugging, and offline evaluation.
2. **Persistent Wiki Layer (`wiki/`)**:
   - Monotonically growing, non-destructive knowledge base containing task-general abstract patterns (`patterns/`), an index overview (`index.md`), changelogs (`log.md`), and historical skill impact metrics (`skill-impact.md`).
   - The Wiki Maintainer summarizes successes and failures into structured failure modes, success principles, and domain rules.
3. **Procedural Skill Layer (`skills/`)**:
   - Condition-action procedural knowledge files formatted as dual-file units:
     - `SKILL.md`: Frontmatter, trigger conditions (When to Apply / When NOT to Apply), and clear step-by-step procedural instructions.
     - `PURPOSE.md`: Origin trace links, target patterns addressed, and evolution change history.

### 2. Four Cooperating Roles (Multi-Agent Cycle)
1. **Inference Agent ($M_{\text{inf}}$)**:
   - Executes incoming domain tasks using active skills and available environment tools.
   - **Critical Rule**: Strictly isolates itself from reading the verbose Wiki layer to prevent token bloat and context distraction (validated by Table 3 in the paper).
2. **Wiki Maintainer ($M_{\text{wiki}}$)**:
   - Ingests batch execution traces $(B_{\tau})$ from `raw/traces/`.
   - Synthesizes domain patterns, failure root causes, and success strategies into structured Markdown articles under `wiki/patterns/`.
3. **Skill Proposer ($M_{\text{prop}}$)**:
   - Reads the newly synthesized patterns and unresolved failure modes from the Wiki layer.
   - Proposes atomic operations: `ADD_SKILL`, `UPDATE_SKILL`, or `REMOVE_SKILL`.
4. **Gating Controller ($M_{\text{gate}}$)**:
   - Validates proposals on a validation set ($D_{\text{val}}$).
   - If performance score improves or stays strictly non-regressive without format violations, commits the change to `skills/` and records acceptance in `wiki/log.md`.
   - If performance degrades, rolls back skill changes atomically while retaining the failure analysis in the Wiki layer for future awareness.

## Practical CLI Commands

In any initialized repository with WikiSkill installed:

```bash
# Check current workspace status (traces, patterns, active skills)
PYTHONPATH=. python3 -m wikiskill.cli status

# Initialize standard three-tier directories and metadata templates
PYTHONPATH=. python3 -m wikiskill.cli init

# Execute the Algorithm 1 evolution loop on train and validation datasets
PYTHONPATH=. python3 -m wikiskill.cli evolve --train data/train.json --val data/val.json --max-iters 5
```

## Python SDK Integration

```python
from wikiskill import WorkspaceManager, WikiSkillOrchestrator, OrchestratorConfig

# Initialize workspace
ws = WorkspaceManager(".")
ws.init_workspace()

# Run evolution
config = OrchestratorConfig(max_iterations=5, early_stop_score=1.0)
orchestrator = WikiSkillOrchestrator(workspace=ws, config=config)
summary = orchestrator.evolve(train_tasks=[...], val_tasks=[...])
print(f"Final Score: {summary.best_score:.4f} with {summary.total_skills} skills.")
```
