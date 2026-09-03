"""
WikiSkill Inference Agent (推理执行体)
对应论文 Section 3.2.1:
- 训练与评估阶段运行 rollouts
- 严格遵循：注入当前激活技能集 S_{k-1}，但对 Wiki 层实行访问隔离（避免训练阶段 Wiki 泄露或直接依赖）
- 产生不可变的原始执行轨迹写入 raw/traces/
"""

import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Callable
from ..storage.workspace import WorkspaceManager


@dataclass
class TaskResult:
    task_id: str
    success: bool
    score: float
    actions_taken: List[Dict[str, Any]]
    observation: str
    error_message: Optional[str] = None
    duration_sec: float = 0.0


class InferenceAgent:
    """
    负责在任务集上执行 rollouts 并将轨迹写入 Raw Layer (raw/traces/)
    """

    def __init__(self, workspace: WorkspaceManager, executor: Optional[Callable[[Dict[str, Any], List[str]], TaskResult]] = None):
        self.workspace = workspace
        self.executor = executor

    def run_rollout(
        self,
        tasks: List[Dict[str, Any]],
        active_skills: Optional[List[str]] = None,
        record_trace: bool = True
    ) -> List[TaskResult]:
        """
        在给定任务列表上执行推理。
        active_skills: 允许注入给推理 agent 的当前生效技能名称列表。
        注意：推理 Agent 严格隔离 Wiki 访问权限。
        """
        results: List[TaskResult] = []
        for task in tasks:
            t_start = time.time()
            task_id = task.get("id") or task.get("task_id", f"task_{int(time.time()*1000)}")

            if self.executor:
                res = self.executor(task, active_skills or [])
            else:
                # 默认模拟/基础执行器
                res = self._default_mock_execute(task, active_skills or [])

            res.duration_sec = round(time.time() - t_start, 3)
            results.append(res)

            if record_trace:
                trace_payload = {
                    "task_id": res.task_id,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "task_desc": task.get("description", ""),
                    "required_skills": task.get("required_skills", []),
                    "active_skills": active_skills or [],
                    "success": res.success,
                    "score": res.score,
                    "actions": res.actions_taken,
                    "observation": res.observation,
                    "error_message": res.error_message,
                    "duration_sec": res.duration_sec
                }
                self.workspace.save_trace(res.task_id, trace_payload)

        return results

    def _default_mock_execute(self, task: Dict[str, Any], active_skills: List[str]) -> TaskResult:
        """根据任务需求和当前技能判断执行结果的基线逻辑"""
        required_skills = task.get("required_skills", [])
        matched = all(req in active_skills for req in required_skills)
        if matched:
            return TaskResult(
                task_id=task.get("id", "unknown"),
                success=True,
                score=1.0,
                actions_taken=[{"action": "apply_skill", "skills": active_skills}],
                observation="Task executed successfully with all required procedural instructions."
            )
        else:
            missing = [req for req in required_skills if req not in active_skills]
            return TaskResult(
                task_id=task.get("id", "unknown"),
                success=False,
                score=0.0,
                actions_taken=[{"action": "attempt", "missing_skills": missing}],
                observation=f"Task failed. Missing procedural guidance: {missing}",
                error_message=f"Lacked skills: {missing}"
            )
