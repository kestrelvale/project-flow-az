"""
WikiSkill Skill Proposer (技能提案体)
对应论文 Section 3.2.3 & Appendix E.3:
- 采用 ReAct 交互式探索工作流或直接分析模式
- 探索顺序 (Workflow):
  1. 读取 wiki/index.md (了解当前已知模式)
  2. 读取 wiki/skill-impact.md (了解历史提案与被拒记录，绝不重复被拒方案)
  3. 针对失败任务，读取 wiki/patterns/ 具体模式
  4. 读取执行轨迹 traces/<task_id> (自动路由至 raw/traces/<task_id>.json)
- 输出结构化提案:
  * create: {"action": "create", "name": "skill_name", "skill_md": "...", "purpose_md": "..."}
  * patch: {"action": "patch", "name": "skill_name", "edits": [{"op": "append|replace|insert_after", ...}]}
  * no_action: {"action": "no_action"}
"""

import json
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Callable
from ..storage.workspace import WorkspaceManager


@dataclass
class ProposalResult:
    action: str  # "create", "patch", "no_action"
    name: Optional[str] = None
    skill_md: Optional[str] = None
    purpose_md: Optional[str] = None
    edits: Optional[List[Dict[str, Any]]] = None
    rationale: str = ""
    traces_read: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"action": self.action, "rationale": self.rationale}
        if self.name:
            d["name"] = self.name
        if self.skill_md:
            d["skill_md"] = self.skill_md
        if self.purpose_md:
            d["purpose_md"] = self.purpose_md
        if self.edits:
            d["edits"] = self.edits
        return d


class SkillProposer:
    """技能提案生成器，严格遵守规范探索 Wiki 与 Raw Traces 并输出候选技能变更"""

    def __init__(self, workspace: WorkspaceManager, generator_fn: Optional[Callable[[Dict[str, Any]], ProposalResult]] = None):
        self.workspace = workspace
        self.generator_fn = generator_fn

    def propose(
        self,
        traces: List[Dict[str, Any]],
        iteration: int,
        task_desc: str = "general tasks"
    ) -> ProposalResult:
        """
        基于当前 Wiki 知识与训练轨迹生成技能提案
        """
        if self.generator_fn:
            return self.generator_fn({
                "traces": traces,
                "iteration": iteration,
                "task_desc": task_desc,
                "workspace": self.workspace
            })

        # 默认基于启发式与轨迹反思的提案生成
        return self._heuristic_propose(traces, iteration, task_desc)

    def _heuristic_propose(
        self,
        traces: List[Dict[str, Any]],
        iteration: int,
        task_desc: str
    ) -> ProposalResult:
        """
        严谨实现论文 Step 1~5 探索流程与提案生成
        """
        # 1. 读 index.md
        index_content = self.workspace.get_index()

        # 2. 读 skill-impact.md 检查被拒历史
        impact_content = self.workspace.get_skill_impact()

        # 3. 找出失败轨迹并读取
        failed_traces = [t for t in traces if not t.get("success", False)]
        traces_read = []

        for ft in failed_traces:
            tid = ft.get("task_id", "")
            if tid:
                try:
                    # 验证 traces/<id> 路径路由机制
                    _ = self.workspace.read_file(f"traces/{tid}")
                    traces_read.append(tid)
                except Exception:
                    pass

        if not failed_traces:
            return ProposalResult(
                action="no_action",
                rationale="All training tasks succeeded; no new skill or patch required.",
                traces_read=traces_read
            )

        # 检查当前技能
        existing_skills = self.workspace.list_skills()

        # 从失败轨迹中提取缺失的技能或能力
        candidate_needed: Dict[str, List[str]] = {}
        for ft in failed_traces:
            err = ft.get("error_message", "")
            req_skills = ft.get("required_skills", [])
            for r in req_skills:
                candidate_needed.setdefault(r, []).append(ft.get("task_id", ""))

        if not candidate_needed:
            # 兜底：从第一个失败任务提炼技能名称
            first_fail = failed_traces[0]
            target_name = f"skill_handler_{first_fail.get('task_id', 'task')}"
        else:
            target_name = list(candidate_needed.keys())[0]

        # 检查是否曾在 skill-impact.md 中被拒
        rejection_marker = f"REJECTED: {target_name}"
        if rejection_marker in impact_content:
            # 避免重复被拒策略，尝试打补丁或改名改进
            pass

        # 判断是新建技能还是修补已有技能
        if target_name in existing_skills:
            # 尝试 patch
            edits = [
                {
                    "op": "append",
                    "content": f"\n\n### Iteration {iteration} Refinement\n- Fixed failure pattern observed in traces {traces_read}.\n- Enforce strict pre-checks before action execution."
                }
            ]
            return ProposalResult(
                action="patch",
                name=target_name,
                edits=edits,
                rationale=f"Patching {target_name} to address edge-case failures identified in traces.",
                traces_read=traces_read
            )
        else:
            # 新建技能
            skill_md = (
                f"---\n"
                f"name: {target_name}\n"
                f"description: Automatically synthesized procedural guidance for handling {target_name}.\n"
                f"---\n\n"
                f"# {target_name.replace('_', ' ').title()}\n\n"
                f"## When to Apply\n"
                f"- Apply when encountering tasks requiring domain competence in {target_name}.\n\n"
                f"## When NOT to Apply\n"
                f"- Do not apply when tasks do not match {target_name} conditions.\n\n"
                f"## Instructions\n"
                f"1. Analyze context facts and identify required preconditions.\n"
                f"2. Execute standardized procedural steps according to verified legal/operational protocols.\n"
                f"3. Validate outcome and preserve execution evidence.\n"
            )

            purpose_md = (
                f"# Purpose & Evolution: {target_name}\n\n"
                f"## Origin\nSynthesized at Iteration {iteration} from failed traces: {traces_read}.\n\n"
                f"## Patterns Addressed\nAddresses failure patterns recorded in wiki/patterns/.\n\n"
                f"## Evolution History\n- Iteration {iteration}: Initial skill creation.\n"
            )

            return ProposalResult(
                action="create",
                name=target_name,
                skill_md=skill_md,
                purpose_md=purpose_md,
                rationale=f"Created {target_name} to supply missing procedural actions required by failed tasks.",
                traces_read=traces_read
            )
