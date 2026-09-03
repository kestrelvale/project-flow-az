"""
WikiSkill Wiki Maintainer (知识沉淀维护体)
对应论文 Section 3.2.2 & Appendix E.2:
- 深度分析执行轨迹 (Root Cause Analysis)，识别失败模式与成功策略
- 对模式进行增量 Patch 或新建：
  * create_patterns: 新模式页面写入 wiki/patterns/
  * update_patterns: 基于 edits (append, replace, insert_after) 增量修补现有模式
  * update_index: 强制重构并更新 index.md，严格遵循格式：
    `- [pattern-name](wiki/patterns/pattern-name.md): PROBLEM + ROOT CAUSE + FIX`
  * append_log: 追加演化时间线到 log.md
- 保证 Wiki 持续复利、永久留存、绝不回滚
"""

import json
from typing import Dict, List, Any, Optional
from ..storage.workspace import WorkspaceManager


class WikiMaintainer:
    """负责将原始任务执行经验提炼沉淀为高质量、高密度的结构化知识库"""

    def __init__(self, workspace: WorkspaceManager):
        self.workspace = workspace

    def consolidate_traces(
        self,
        traces: List[Dict[str, Any]],
        iteration: int,
        custom_analysis_fn: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        从采样的执行轨迹中提炼模式并更新 Wiki
        """
        if custom_analysis_fn:
            maintainer_output = custom_analysis_fn(traces, self.workspace, iteration)
        else:
            maintainer_output = self._heuristic_analyze_traces(traces, iteration)

        # 1. 落地 create_patterns
        created = []
        for item in maintainer_output.get("create_patterns", []):
            name = item["name"]
            content = item["content"]
            self.workspace.create_pattern(name, content)
            created.append(name)

        # 2. 落地 update_patterns (增量 patch)
        updated = []
        for item in maintainer_output.get("update_patterns", []):
            name = item["name"]
            edits = item["edits"]
            self.workspace.patch_pattern(name, edits)
            updated.append(name)

        # 3. 强制更新 index.md
        if "update_index" in maintainer_output:
            self.workspace.update_index(maintainer_output["update_index"])

        # 4. 追加 log.md
        log_entry = maintainer_output.get("append_log", "")
        if log_entry:
            self.workspace.append_log(log_entry)

        return {
            "iteration": iteration,
            "created_patterns": created,
            "updated_patterns": updated,
            "log_entry": log_entry
        }

    def _heuristic_analyze_traces(self, traces: List[Dict[str, Any]], iteration: int) -> Dict[str, Any]:
        """
        根据轨迹启发式生成模式定义、更新 index 与 log
        """
        failures = [t for t in traces if not t.get("success", False)]
        successes = [t for t in traces if t.get("success", False)]

        create_patterns = []
        index_entries = []

        # 读取已有 patterns，避免重复创建
        existing_patterns = set(self.workspace.list_patterns())

        for fail in failures:
            task_desc = fail.get("task_desc", "unnamed_task")
            error_msg = fail.get("error_message", "Unknown error")
            pat_name = f"failure_mode_{fail.get('task_id', 'task')}.md"

            if pat_name not in existing_patterns:
                content = (
                    f"# Pattern: {task_desc}\n\n"
                    f"## Description\nTask failed due to lack of procedural guidance.\n\n"
                    f"## Root Cause\nError: {error_msg}. Missing systematic action protocol.\n\n"
                    f"## Exact Action Patterns\n- Attempted: {fail.get('actions', [])}\n\n"
                    f"## Solutions and Workarounds\n- Establish strict pre-conditions, concrete checklist and validated recovery steps.\n"
                )
                create_patterns.append({"name": pat_name, "content": content})
                index_entries.append(
                    f"- [{pat_name}](wiki/patterns/{pat_name}): PROBLEM: {task_desc} failed + "
                    f"ROOT CAUSE: {error_msg} + FIX: Follow validated checklist and recovery actions."
                )

        # 构建新的 index 内容（保留旧项，追加新项）
        current_index = self.workspace.get_index()
        for entry in index_entries:
            if entry not in current_index:
                current_index += entry + "\n"

        log_summary = f"| Iteration {iteration} | Analyzed {len(traces)} traces ({len(successes)} pass, {len(failures)} fail) | Created {len(create_patterns)} new patterns | Wiki compounded |"

        return {
            "create_patterns": create_patterns,
            "update_patterns": [],
            "update_index": current_index,
            "append_log": log_summary
        }
