"""
WikiSkill Gating & Rollback Controller (验证门控与回滚控制器)
对应论文 Section 3.2.4 & Algorithm 1 Lines 12-18:
- 评估验证集表现 R(T_{val,k})
- 门控判据：
  * 若 R(T_{val,k}) > R_best：接受候选技能 S'_k，更新 R_best，标记 a_k = Accepted
  * 否则：回滚技能至 S_{k-1}，保持 R_best 不变，标记 a_k = Rejected
- 关键论文保证：
  * 回滚只作用于 skills/ 层（通过 WorkspaceManager 快照机制安全恢复）
  * Wiki 层永不回滚，并在 wiki/skill-impact.md 中忠实记录提案内容、验证得分及拒识/采纳审计日志（供未来 Proposer 规避死胡同）
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from ..storage.workspace import WorkspaceManager
from .proposer import ProposalResult
from .inference import TaskResult


@dataclass
class EvaluationResult:
    score: float
    passed_count: int
    total_count: int
    accepted: bool
    best_score_before: float
    best_score_after: float
    details: List[Dict[str, Any]]


class GatingController:
    """负责在验证集上检验候选技能有效性，并严格执行条件回滚与审计沉淀"""

    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace

    def evaluate_and_gate(
        self,
        val_results: List[TaskResult],
        proposal: ProposalResult,
        iteration: int,
        r_best: float
    ) -> EvaluationResult:
        """
        根据验证集表现判断是否接纳 proposal。
        严格遵循 Algorithm 1:
        if R(T_{val,k}) > R_best then
            S_k <- S'_k, R_best <- R(T_{val,k}), a_k <- Accepted
        else
            S_k <- S_{k-1}, a_k <- Rejected (Roll back skills only; wiki retained)
        """
        if not val_results:
            score = 0.0
            passed = 0
            total = 0
        else:
            total = len(val_results)
            passed = sum(1 for r in val_results if r.success)
            score = round(sum(r.score for r in val_results) / total, 4)

        # 严格门控：必须严格优于历史最佳 R_best (或初始 baseline)
        accepted = score > r_best
        new_best = score if accepted else r_best

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # 构造审计信息记录至 wiki/skill-impact.md
        audit_block = (
            f"### Iteration {iteration} - {timestamp}\n"
            f"- **Status**: {'ACCEPTED' if accepted else 'REJECTED'}\n"
            f"- **Action**: {proposal.action} ({proposal.name or 'N/A'})\n"
            f"- **Validation Score**: {score:.4f} (Previous Best: {r_best:.4f}, Passed: {passed}/{total})\n"
            f"- **Rationale**: {proposal.rationale}\n"
        )

        if not accepted:
            # 记录被拒提案详情，防止未来 Proposer 重蹈覆辙
            audit_block += (
                f"- **Rejected Proposal Dump**:\n"
                f"  - Target: {proposal.name}\n"
                f"  - Action Type: {proposal.action}\n"
            )
            if proposal.edits:
                audit_block += f"  - Attempted Edits: {proposal.edits}\n"
            audit_block += f"- **Rollback**: Restored skills/ to pre-proposal state. Wiki preserved.\n\n"
            # 执行技能回滚
            self.workspace.rollback_skills()
        else:
            audit_block += f"- **Commit**: New skill configuration accepted and committed.\n\n"
            # 提交并清理快照
            self.workspace.commit_skills_snapshot()

        # 追加写入永久审计追踪文件
        self.workspace.append_skill_impact(audit_block)

        return EvaluationResult(
            score=score,
            passed_count=passed,
            total_count=total,
            accepted=accepted,
            best_score_before=r_best,
            best_score_after=new_best,
            details=[{"task_id": r.task_id, "score": r.score, "success": r.success} for r in val_results]
        )
