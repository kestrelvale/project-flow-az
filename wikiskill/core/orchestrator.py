"""
WikiSkill 闭环主控调度器 (WikiSkill Orchestrator)
严格实现论文 arXiv:2608.27454 Algorithm 1: WikiSkill evolution loop
1. Baseline Validation: R_best <- R(T_{val,0}) with initial skills S_0 (empty or seed)
2. 迭代演化循环 (k = 1 ... K):
   a. Termination check: if R_best == 1.0, break early
   b. Inference: Roll out T_{train,k} on training tasks using active skills S_{k-1}
   c. Sample subset: T_{sample,k} from T_{train,k}
   d. Wiki Maintenance: W'_k <- Maintainer(W_{k-1}, T_{sample,k})
   e. Skill Proposal: P_k <- Proposer(W'_k, S_{k-1}, T_{train,k})
   f. Apply: Snapshot skills and apply P_k -> S'_k
   g. Validate: T_{val,k} <- Roll out on validation tasks using candidate skills S'_k
   h. Gating & Decision:
      if R(T_{val,k}) > R_best:
          S_k <- S'_k, R_best <- R(T_{val,k}), a_k <- Accepted
      else:
          S_k <- S_{k-1}, a_k <- Rejected (Roll back skills only; wiki retained)
   i. Update Wiki Log: append audit, diffs, metrics to logs.md and skill-impact.md
3. Return S_K, W_K
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from ..storage.workspace import WorkspaceManager
from .inference import InferenceAgent, TaskResult
from .maintainer import WikiMaintainer
from .proposer import SkillProposer, ProposalResult
from .gating import GatingController, EvaluationResult


@dataclass
class OrchestratorConfig:
    max_iterations: int = 5
    early_stop_score: float = 1.0
    sample_ratio: float = 1.0
    verbose: bool = True


@dataclass
class EvolutionIterationReport:
    iteration: int
    train_pass_rate: float
    val_score: float
    r_best: float
    action: str
    accepted: bool
    proposal: Dict[str, Any]
    patterns_created: List[str]
    patterns_updated: List[str]


@dataclass
class EvolutionSummary:
    initial_score: float
    final_score: float
    best_score: float
    iterations_run: int
    total_skills: int
    total_patterns: int
    accepted_proposals: int
    rejected_proposals: int
    iterations: List[EvolutionIterationReport] = field(default_factory=list)


class WikiSkillOrchestrator:
    """Algorithm 1 闭环执行器，驱动 Inference, Maintainer, Proposer, Gating 协同演进"""

    def __init__(
        self,
        workspace: WorkspaceManager,
        config: Optional[OrchestratorConfig] = None,
        inference_agent: Optional[InferenceAgent] = None,
        maintainer: Optional[WikiMaintainer] = None,
        proposer: Optional[SkillProposer] = None,
        gating: Optional[GatingController] = None
    ):
        self.workspace = workspace
        self.config = config or OrchestratorConfig()
        self.workspace.init_workspace()

        self.inference_agent = inference_agent or InferenceAgent(workspace=self.workspace)
        self.maintainer = maintainer or WikiMaintainer(workspace=self.workspace)
        self.proposer = proposer or SkillProposer(workspace=self.workspace)
        self.gating = gating or GatingController(workspace=self.workspace)

    def evolve(
        self,
        train_tasks: List[Dict[str, Any]],
        val_tasks: List[Dict[str, Any]],
        metric_fn: Optional[Callable[[List[TaskResult]], float]] = None
    ) -> EvolutionSummary:
        """
        严格按照 Algorithm 1 执行演进闭环
        """
        # 1. Baseline Validation (Lines 1-2)
        active_skills = self.workspace.list_skills()
        val_baseline = self.inference_agent.run_rollout(
            tasks=val_tasks,
            active_skills=active_skills,
            record_trace=False
        )

        if metric_fn:
            r_best = metric_fn(val_baseline)
        else:
            r_best = round(sum(r.score for r in val_baseline) / len(val_baseline), 4) if val_baseline else 0.0

        initial_score = r_best
        accepted_count = 0
        rejected_count = 0
        reports: List[EvolutionIterationReport] = []

        if self.config.verbose:
            print(f"[WikiSkill] === Baseline Validation Score: {r_best:.4f} (Active skills: {len(active_skills)}) ===")

        # 2. Iteration Loop (Lines 3-19)
        for k in range(1, self.config.max_iterations + 1):
            if r_best >= self.config.early_stop_score:
                if self.config.verbose:
                    print(f"[WikiSkill] Early stopping reached at iteration {k-1}: score = {r_best:.4f}")
                break

            if self.config.verbose:
                print(f"\n[WikiSkill] >>> Iteration {k}/{self.config.max_iterations} (Current Best: {r_best:.4f})")

            # 7: Inference on train tasks using S_{k-1}
            active_skills = self.workspace.list_skills()
            train_results = self.inference_agent.run_rollout(
                tasks=train_tasks,
                active_skills=active_skills,
                record_trace=True
            )
            train_pass_rate = sum(1 for r in train_results if r.success) / len(train_results) if train_results else 0.0

            # 8: Sample subset (论文中取子集；默认全量或按比率采样)
            train_traces = []
            for r in train_results:
                tr = self.workspace.load_trace(r.task_id)
                if tr:
                    train_traces.append(tr)
                else:
                    train_traces.append({
                        "task_id": r.task_id,
                        "success": r.success,
                        "score": r.score,
                        "error_message": r.error_message,
                        "actions": r.actions_taken
                    })

            sample_size = max(1, int(len(train_traces) * self.config.sample_ratio))
            sample_traces = train_traces[:sample_size]

            # 9: Wiki Maintenance: W'_k <- MWM(W_{k-1}, T_{sample,k})
            maintainer_res = self.maintainer.consolidate_traces(sample_traces, iteration=k)

            # 10: Skill Proposal: P_k <- MP(W'_k, S_{k-1}, T_{train,k})
            proposal = self.proposer.propose(train_traces, iteration=k)

            # 11: Apply: S'_k <- Apply(S_{k-1}, P_k)
            # 在应用前做快照
            self.workspace.snapshot_skills()
            if proposal.action == "create" and proposal.name and proposal.skill_md:
                self.workspace.create_skill(
                    skill_name=proposal.name,
                    skill_md=proposal.skill_md,
                    purpose_md=proposal.purpose_md or ""
                )
            elif proposal.action == "patch" and proposal.name and proposal.edits:
                try:
                    self.workspace.patch_skill(proposal.name, proposal.edits)
                except Exception as e:
                    # 补丁失败视为提案非法
                    pass

            # 12: Validate on validation tasks using candidate skills S'_k
            candidate_skills = self.workspace.list_skills()
            val_results = self.inference_agent.run_rollout(
                tasks=val_tasks,
                active_skills=candidate_skills,
                record_trace=False
            )

            # 13-17: Gating check & conditional rollback
            eval_res = self.gating.evaluate_and_gate(
                val_results=val_results,
                proposal=proposal,
                iteration=k,
                r_best=r_best
            )

            if eval_res.accepted:
                accepted_count += 1
                r_best = eval_res.best_score_after
            else:
                rejected_count += 1

            # 18: Update Wiki Log (logs.md 记录表格行)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_line = (
                f"| {k} | {timestamp} | {train_pass_rate*100:.1f}% | {eval_res.score:.4f} | "
                f"{proposal.action} ({'Accepted' if eval_res.accepted else 'Rejected'}) | "
                f"{proposal.rationale[:60]}... |\n"
            )
            self.workspace.append_log(log_line)

            report = EvolutionIterationReport(
                iteration=k,
                train_pass_rate=train_pass_rate,
                val_score=eval_res.score,
                r_best=r_best,
                action=proposal.action,
                accepted=eval_res.accepted,
                proposal=proposal.to_dict(),
                patterns_created=maintainer_res.get("created_patterns", []),
                patterns_updated=maintainer_res.get("updated_patterns", [])
            )
            reports.append(report)

            if self.config.verbose:
                print(f"[WikiSkill] Iteration {k} Result: Action={proposal.action} ({proposal.name or 'none'}), "
                      f"Accepted={eval_res.accepted}, Val Score={eval_res.score:.4f}, Best={r_best:.4f}")

        # 20: return S_K, W_K
        final_skills = self.workspace.list_skills()
        final_patterns = self.workspace.list_patterns()

        summary = EvolutionSummary(
            initial_score=initial_score,
            final_score=r_best,
            best_score=r_best,
            iterations_run=len(reports),
            total_skills=len(final_skills),
            total_patterns=len(final_patterns),
            accepted_proposals=accepted_count,
            rejected_proposals=rejected_count,
            iterations=reports
        )
        return summary
