import shutil
import tempfile
from pathlib import Path
from wikiskill.storage.workspace import WorkspaceManager
from wikiskill.core.orchestrator import WikiSkillOrchestrator, OrchestratorConfig
from wikiskill.core.inference import InferenceAgent, TaskResult
from wikiskill.core.maintainer import WikiMaintainer
from wikiskill.core.proposer import SkillProposer, ProposalResult
from wikiskill.core.gating import GatingController


def test_orchestrator_evolution_loop():
    tmp_dir = tempfile.mkdtemp(prefix="wikiskill_orch_test_")
    try:
        ws = WorkspaceManager(tmp_dir)
        ws.init_workspace()

        # 定义训练与验证任务
        train_tasks = [
            {"id": "t1", "description": "Draft relocation refusal", "required_skills": ["relocation_rebuttal"]},
            {"id": "t2", "description": "Constructive dismissal dual notice", "required_skills": ["relocation_rebuttal", "constructive_dismissal"]}
        ]
        val_tasks = [
            {"id": "v1", "description": "Validate relocation handling", "required_skills": ["relocation_rebuttal"]},
            {"id": "v2", "description": "Validate dual notice handling", "required_skills": ["constructive_dismissal"]}
        ]

        cfg = OrchestratorConfig(max_iterations=3, early_stop_score=1.0, verbose=False)
        orch = WikiSkillOrchestrator(workspace=ws, config=cfg)

        summary = orch.evolve(train_tasks=train_tasks, val_tasks=val_tasks)

        # 检验演化产物
        assert summary.iterations_run >= 1
        assert summary.final_score >= summary.initial_score
        assert len(ws.list_patterns()) >= 1
        assert (ws.wiki_dir / "index.md").exists()
        assert (ws.wiki_dir / "log.md").exists()
        assert (ws.wiki_dir / "skill-impact.md").exists()

        # 检查 skills 目录
        skills = ws.list_skills()
        assert len(skills) >= 1
        for s in skills:
            s_dir = ws.skills_dir / s
            assert (s_dir / "SKILL.md").exists()
            assert (s_dir / "PURPOSE.md").exists()
    finally:
        shutil.rmtree(tmp_dir)


def test_gating_rollback_preserves_wiki():
    tmp_dir = tempfile.mkdtemp(prefix="wikiskill_gating_test_")
    try:
        ws = WorkspaceManager(tmp_dir)
        ws.init_workspace()

        # 创建一个已有技能
        ws.create_skill(
            skill_name="base_skill",
            skill_md="---\nname: base_skill\n---\n# Base Skill\nOriginal content",
            purpose_md="# Purpose\nOriginal"
        )

        gating = GatingController(ws)

        # 准备一个失败提案
        ws.snapshot_skills()
        ws.create_skill(
            skill_name="bad_skill",
            skill_md="---\nname: bad_skill\n---\n# Bad",
            purpose_md="# Bad"
        )
        assert "bad_skill" in ws.list_skills()

        # 模拟评估结果：得分为 0.2，低于之前的最好分数 0.8
        val_results = [
            TaskResult(task_id="v1", success=False, score=0.2, actions_taken=[], observation="Failed")
        ]
        proposal = ProposalResult(action="create", name="bad_skill", rationale="Experimental bad skill")

        eval_res = gating.evaluate_and_gate(
            val_results=val_results,
            proposal=proposal,
            iteration=1,
            r_best=0.8
        )

        assert not eval_res.accepted
        # 验证 skills/ 已回滚：bad_skill 应该被移除了，base_skill 还在
        current_skills = ws.list_skills()
        assert "bad_skill" not in current_skills
        assert "base_skill" in current_skills

        # 验证 wiki/skill-impact.md 中忠实记录了被拒绝历史
        impact_log = ws.get_skill_impact()
        assert "REJECTED" in impact_log
        assert "bad_skill" in impact_log
    finally:
        shutil.rmtree(tmp_dir)
