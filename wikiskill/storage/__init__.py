"""
WikiSkill 存储与工作区管理层
实现论文中的三层架构：raw/ (只追加)、wiki/ (永不回滚)、skills/ (条件回滚)
"""

from .workspace import WorkspaceManager
from .patch import apply_patches, PatchOperationError

__all__ = ["WorkspaceManager", "apply_patches", "PatchOperationError"]
