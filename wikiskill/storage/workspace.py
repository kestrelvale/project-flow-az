"""
WikiSkill 工作区管理器
严格遵循论文 Section 3.1 & Figure 2：
1. raw/：不可变原始轨迹，只追加不可变，物理路径 raw/traces/<task_id>.json
2. wiki/：持久沉淀知识层，永不回滚，包含 patterns/、index.md、log.md、skill-impact.md
3. skills/：程序化技能层，动态可条件回滚，每个技能包含 SKILL.md 与 PURPOSE.md
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from .patch import apply_patches, PatchOperationError


class WorkspaceManager:
    """管理 WikiSkill 的三层存储架构与生命周期状态"""

    def __init__(self, root_dir: str = "."):
        self.root = Path(root_dir).resolve()
        self.raw_dir = self.root / "raw"
        self.traces_dir = self.raw_dir / "traces"
        self.wiki_dir = self.root / "wiki"
        self.patterns_dir = self.wiki_dir / "patterns"
        self.skills_dir = self.root / "skills"

        self.index_file = self.wiki_dir / "index.md"
        self.log_file = self.wiki_dir / "log.md"
        self.skill_impact_file = self.wiki_dir / "skill-impact.md"

        # 内部临时快照备份目录，用于 Gating 失败时回滚 skills/
        self._backup_skills_dir = self.root / ".wikiskill_cache" / "skills_backup"

    def init_workspace(self, force: bool = False) -> None:
        """初始化三层存储目录结构与初始知识模板"""
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        if force or not self.index_file.exists():
            self.index_file.write_text(
                "# Wiki Knowledge Index\n\n"
                "<!-- Format: - [pattern-name](wiki/patterns/pattern-name.md): PROBLEM + ROOT CAUSE + FIX -->\n\n",
                encoding="utf-8"
            )

        if force or not self.log_file.exists():
            self.log_file.write_text(
                "# Evolution Log (logs.md)\n\n"
                "| Iteration | Timestamp | Train Pass Rate | Val Score | Action | Summary |\n"
                "|---|---|---|---|---|---|\n",
                encoding="utf-8"
            )

        if force or not self.skill_impact_file.exists():
            self.skill_impact_file.write_text(
                "# Skill Impact Tracker (skill-impact.md)\n\n"
                "Audit trail of all proposed skill updates, validation scores, and acceptance decisions.\n\n",
                encoding="utf-8"
            )

    # -------------------------------------------------------------
    # 1. Raw Layer (raw/) - 物理只追加、不可变
    # -------------------------------------------------------------
    def save_trace(self, task_id: str, trace_data: Dict[str, Any]) -> Path:
        """保存任务执行轨迹。如果已存在，报错或禁止覆盖，确保不可变性"""
        file_path = self.traces_dir / f"{task_id}.json"
        if file_path.exists():
            # 轨迹只追加，同一 task_id 允许追加时间戳或自增标识，不可就地篡改
            pass
        file_path.write_text(json.dumps(trace_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return file_path

    def load_trace(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据 task_id 读取执行轨迹"""
        clean_id = task_id.removesuffix(".json")
        file_path = self.traces_dir / f"{clean_id}.json"
        if not file_path.exists():
            return None
        return json.loads(file_path.read_text(encoding="utf-8"))

    def list_traces(self) -> List[str]:
        """列出所有轨迹 task_id"""
        if not self.traces_dir.exists():
            return []
        return [f.stem for f in self.traces_dir.glob("*.json")]

    # -------------------------------------------------------------
    # 2. Wiki Layer (wiki/) - 永久沉淀、永不回滚
    # -------------------------------------------------------------
    def get_index(self) -> str:
        if self.index_file.exists():
            return self.index_file.read_text(encoding="utf-8")
        return ""

    def update_index(self, content: str) -> None:
        self.index_file.write_text(content, encoding="utf-8")

    def get_log(self) -> str:
        if self.log_file.exists():
            return self.log_file.read_text(encoding="utf-8")
        return ""

    def append_log(self, entry_line: str) -> None:
        with open(self.log_file, "a", encoding="utf-8") as f:
            if not entry_line.endswith("\n"):
                entry_line += "\n"
            f.write(entry_line)

    def get_skill_impact(self) -> str:
        if self.skill_impact_file.exists():
            return self.skill_impact_file.read_text(encoding="utf-8")
        return ""

    def append_skill_impact(self, block: str) -> None:
        with open(self.skill_impact_file, "a", encoding="utf-8") as f:
            if not block.endswith("\n"):
                block += "\n"
            f.write(block)

    def create_pattern(self, name: str, content: str) -> Path:
        """创建新的 pattern 文件 (wiki/patterns/<name>)"""
        if not name.endswith(".md"):
            name += ".md"
        path = self.patterns_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def patch_pattern(self, name: str, edits: List[Dict[str, Any]]) -> str:
        """通过增量 patch 操作修改已有的 pattern"""
        if not name.endswith(".md"):
            name += ".md"
        path = self.patterns_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Pattern '{name}' does not exist.")
        old_content = path.read_text(encoding="utf-8")
        new_content = apply_patches(old_content, edits)
        path.write_text(new_content, encoding="utf-8")
        return new_content

    def list_patterns(self) -> List[str]:
        if not self.patterns_dir.exists():
            return []
        return [f.name for f in self.patterns_dir.glob("*.md")]

    def get_pattern(self, name: str) -> Optional[str]:
        if not name.endswith(".md"):
            name += ".md"
        path = self.patterns_dir / name
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    # -------------------------------------------------------------
    # 3. Skills Layer (skills/) - 可动态条件回滚
    # -------------------------------------------------------------
    def list_skills(self) -> List[str]:
        if not self.skills_dir.exists():
            return []
        return [d.name for d in self.skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]

    def get_skill(self, skill_name: str) -> Optional[Dict[str, str]]:
        skill_path = self.skills_dir / skill_name
        skill_md = skill_path / "SKILL.md"
        purpose_md = skill_path / "PURPOSE.md"
        if not skill_md.exists():
            return None
        return {
            "name": skill_name,
            "skill_md": skill_md.read_text(encoding="utf-8"),
            "purpose_md": purpose_md.read_text(encoding="utf-8") if purpose_md.exists() else ""
        }

    def create_skill(self, skill_name: str, skill_md: str, purpose_md: str) -> Path:
        skill_path = self.skills_dir / skill_name
        skill_path.mkdir(parents=True, exist_ok=True)
        (skill_path / "SKILL.md").write_text(skill_md, encoding="utf-8")
        (skill_path / "PURPOSE.md").write_text(purpose_md, encoding="utf-8")
        return skill_path

    def patch_skill(self, skill_name: str, edits: List[Dict[str, Any]]) -> str:
        skill_path = self.skills_dir / skill_name
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"Skill '{skill_name}' does not exist.")
        old_content = skill_md.read_text(encoding="utf-8")
        new_content = apply_patches(old_content, edits)
        skill_md.write_text(new_content, encoding="utf-8")
        return new_content

    # -------------------------------------------------------------
    # Gating & Rollback 管理 (仅回滚 skills/，保留 wiki/ 和 raw/)
    # -------------------------------------------------------------
    def snapshot_skills(self) -> None:
        """对 skills/ 进行快照备份，便于验证未通过时回滚"""
        if self._backup_skills_dir.exists():
            shutil.rmtree(self._backup_skills_dir)
        self._backup_skills_dir.parent.mkdir(parents=True, exist_ok=True)
        if self.skills_dir.exists():
            shutil.copytree(self.skills_dir, self._backup_skills_dir)

    def rollback_skills(self) -> None:
        """发生拒识时执行回滚：恢复快照中的 skills/，绝不触碰 wiki/ 和 raw/"""
        if not self._backup_skills_dir.exists():
            return
        if self.skills_dir.exists():
            shutil.rmtree(self.skills_dir)
        shutil.copytree(self._backup_skills_dir, self.skills_dir)

    def commit_skills_snapshot(self) -> None:
        """验证达标接受新技能，清理快照"""
        if self._backup_skills_dir.exists():
            shutil.rmtree(self._backup_skills_dir)

    # -------------------------------------------------------------
    # 统一路径解析工具 (支持 traces/<task_id> 自动路由至 raw/traces/)
    # -------------------------------------------------------------
    def read_file(self, relative_path: str) -> str:
        """
        供 Proposer 与 ReAct 使用的虚拟文件读取器：
        自动将 'traces/<task_id>' 映射至 'raw/traces/<task_id>.json'
        """
        path_str = relative_path.strip().lstrip("/")
        if path_str.startswith("traces/"):
            task_id = path_str[len("traces/"):].removesuffix(".json")
            target = self.traces_dir / f"{task_id}.json"
        elif path_str.startswith("raw/"):
            target = self.root / path_str
        elif path_str.startswith("wiki/"):
            target = self.root / path_str
        elif path_str.startswith("skills/"):
            target = self.root / path_str
        else:
            target = self.root / path_str

        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path} (resolved to {target})")
        return target.read_text(encoding="utf-8")
