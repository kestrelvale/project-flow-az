"""
WikiSkill 增量 Patch 引擎
支持论文 Appendix E.2 与 E.3 规范的操作：
- append: 追加内容到末尾
- replace: 精确子串替换
- insert_after: 在目标子串之后插入
"""

from typing import List, Dict, Any


class PatchOperationError(Exception):
    """Patch 操作失败异常"""
    pass


def apply_patches(original_content: str, edits: List[Dict[str, Any]]) -> str:
    """
    按顺序对文本应用 patch 操作列表
    """
    content = original_content
    for idx, edit in enumerate(edits):
        op = edit.get("op")
        if not op:
            raise PatchOperationError(f"Edit #{idx} missing 'op' field: {edit}")

        if op == "append":
            text_to_add = edit.get("content", "")
            if content and not content.endswith("\n") and text_to_add and not text_to_add.startswith("\n"):
                content += "\n" + text_to_add
            else:
                content += text_to_add

        elif op == "replace":
            target = edit.get("target")
            replacement = edit.get("content", "")
            if target is None:
                raise PatchOperationError(f"Edit #{idx} op='replace' missing 'target'")
            if target not in content:
                raise PatchOperationError(
                    f"Edit #{idx} op='replace' failed: target substring not found: {repr(target)[:80]}"
                )
            # 仅替换首次出现的匹配项（或者精确替换）
            content = content.replace(target, replacement, 1)

        elif op == "insert_after":
            target = edit.get("target")
            insertion = edit.get("content", "")
            if target is None:
                raise PatchOperationError(f"Edit #{idx} op='insert_after' missing 'target'")
            if target not in content:
                raise PatchOperationError(
                    f"Edit #{idx} op='insert_after' failed: target substring not found: {repr(target)[:80]}"
                )
            pos = content.find(target) + len(target)
            content = content[:pos] + insertion + content[pos:]

        else:
            raise PatchOperationError(f"Edit #{idx} unsupported operation '{op}'")

    return content
