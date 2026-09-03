"""
WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution
Reference: arXiv:2608.27454 (Google Research & Virginia Tech, 2026)
"""

from .storage.workspace import WorkspaceManager
from .storage.patch import apply_patches, PatchOperationError
from .core.inference import InferenceAgent, TaskResult
from .core.maintainer import WikiMaintainer
from .core.proposer import SkillProposer, ProposalResult
from .core.gating import GatingController, EvaluationResult
from .core.orchestrator import WikiSkillOrchestrator, OrchestratorConfig, EvolutionSummary

__version__ = "1.0.0"

__all__ = [
    "WorkspaceManager",
    "apply_patches",
    "PatchOperationError",
    "InferenceAgent",
    "TaskResult",
    "WikiMaintainer",
    "SkillProposer",
    "ProposalResult",
    "GatingController",
    "EvaluationResult",
    "WikiSkillOrchestrator",
    "OrchestratorConfig",
    "EvolutionSummary",
]
