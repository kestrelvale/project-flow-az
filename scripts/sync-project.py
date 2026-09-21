#!/usr/bin/env python3
import sys
import os
import shutil


START_MARKER = "<!-- project-flow-cy:start -->"
END_MARKER = "<!-- project-flow-cy:end -->"
HISTORY_DIRS = ("plans", "tasks", "progress")
TRASH_DIRS = ("deprecated", "verification")


def sync_agents_runtime_contract(template_text, target_file):
    """
    只维护标记块内的 project-flow 运行时合同，块外内容一律保留。
    已有项目没有标记块时，将合同块插入到标题与说明之后。
    """
    start = template_text.find(START_MARKER)
    end = template_text.find(END_MARKER)
    if start == -1 or end == -1 or end <= start:
        return
    contract = template_text[start:end + len(END_MARKER)]

    if not os.path.exists(target_file):
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(template_text)
        return

    with open(target_file, "r", encoding="utf-8") as f:
        current = f.read()

    if START_MARKER in current and END_MARKER in current:
        old_start = current.index(START_MARKER)
        old_end = current.index(END_MARKER, old_start) + len(END_MARKER)
        updated = current[:old_start] + contract + current[old_end:]
    else:
        lines = current.splitlines()
        insert_at = 0
        # 跳过标题与首段说明，保证运行时合同尽早出现在入口文件中。
        while insert_at < len(lines) and (not lines[insert_at].strip() or lines[insert_at].startswith("#") or lines[insert_at].startswith(">")):
            insert_at += 1
            if insert_at < len(lines) and not lines[insert_at].strip():
                break
        head = "\n".join(lines[:insert_at]).rstrip()
        tail = "\n".join(lines[insert_at:]).lstrip()
        updated = (head + "\n\n" + contract + "\n\n" + tail).strip() + "\n"

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(updated)


def retire_technical_debt(target_dir, flow_dir, trash_dir):
    """
    V4.0 自动更新后技术债回收机制 (Post-Update Technical Debt GC):
    在项目热同步或版本升级后，自动物理清除历史遗留的僵尸配置、阻塞式 Hook 及过渡期碎片文件。
    """
    cleaned_items = []

    # 回收过度实体碎片 (Purge Deprecated Transition Files, e.g. checklist.md)
    checklist_path = os.path.join(flow_dir, "checklist.md")
    if os.path.exists(checklist_path):
        trash_checklist = os.path.join(trash_dir, "checklist_retired_v4.md")
        try:
            shutil.move(checklist_path, trash_checklist)
            cleaned_items.append("回收过渡期 checklist.md 实体至 flow/trash/ (收敛为 plan + history 极简架构)")
        except Exception:
            pass

    # 进展日志滚动截断 (Rolling Progress GC)
    progress_path = os.path.join(flow_dir, "进展.md")
    if os.path.exists(progress_path):
        with open(progress_path, "r", encoding="utf-8", errors="ignore") as f:
            progress_content = f.read()
        entries = progress_content.split("\n## ")
        if len(entries) > 3: # Title + >2 entries
            header = entries[0]
            top_entries = entries[1:3]
            archived_entries = entries[3:]
            new_content = header + "\n## " + "\n## ".join(top_entries)
            archive_path = os.path.join(flow_dir, "history", "progress", "进展_archive.md")
            os.makedirs(os.path.dirname(archive_path), exist_ok=True)
            with open(archive_path, "a", encoding="utf-8") as f:
                f.write("\n## " + "\n## ".join(archived_entries))
            with open(progress_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            cleaned_items.append("滚动归档 flow/进展.md 超限历史记录至 flow/history/progress/")

    if cleaned_items:
        print("🧹 [技术债自动回收] 本次自动更新成功清理以下技术债:")
        for item in cleaned_items:
            print(f"   - {item}")


def ensure_archive_layout(flow_dir):
    """补齐四区归档结构，并迁移旧版混放目录，不改任务内容和验收状态。"""
    moved = []
    history_dir = os.path.join(flow_dir, "history")
    trash_dir = os.path.join(flow_dir, "trash")
    for name in HISTORY_DIRS:
        os.makedirs(os.path.join(history_dir, name), exist_ok=True)
    for name in TRASH_DIRS:
        os.makedirs(os.path.join(trash_dir, name), exist_ok=True)
    os.makedirs(os.path.join(flow_dir, "gc", "receipts"), exist_ok=True)

    legacy_progress = os.path.join(history_dir, "进展_archive.md")
    if os.path.exists(legacy_progress):
        destination = os.path.join(history_dir, "progress", "进展_archive.md")
        if not os.path.exists(destination):
            shutil.move(legacy_progress, destination)
            moved.append("history/进展_archive.md -> history/progress/进展_archive.md")

    legacy_verification = os.path.join(trash_dir, "verification-gc")
    if os.path.exists(legacy_verification):
        destination = os.path.join(trash_dir, "verification", "legacy-verification-gc")
        if not os.path.exists(destination):
            shutil.move(legacy_verification, destination)
            moved.append("trash/verification-gc -> trash/verification/legacy-verification-gc")
    return moved

def main():
    if len(sys.argv) < 3:
        print("Usage: sync-project.py <SKILL_DIR> <TARGET_DIR>")
        sys.exit(1)

    skill_dir = os.path.abspath(sys.argv[1])
    target_dir = os.path.abspath(sys.argv[2])

    version_file = os.path.join(skill_dir, "VERSION")
    version = "4.0.0"
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            version = f.read().strip()

    # 1. Ensure directories exist
    flow_dir = os.path.join(target_dir, "flow")
    spec_dir = os.path.join(flow_dir, "规范")
    history_dir = os.path.join(flow_dir, "history")
    trash_dir = os.path.join(flow_dir, "trash")
    tasks_dir = os.path.join(flow_dir, "tasks")
    docs_dir = os.path.join(target_dir, "docs")

    for d in [flow_dir, spec_dir, history_dir, trash_dir, tasks_dir, docs_dir]:
        os.makedirs(d, exist_ok=True)
    moved = ensure_archive_layout(flow_dir)

    # 2. Sync all SOP files into flow/规范/
    references_dir = os.path.join(skill_dir, "references")
    if os.path.exists(references_dir):
        for fname in os.listdir(references_dir):
            if fname.endswith(".md"):
                src = os.path.join(references_dir, fname)
                dst = os.path.join(spec_dir, fname)
                shutil.copy2(src, dst)

    # 3. Write flow/规范/VERSION
    with open(os.path.join(spec_dir, "VERSION"), "w", encoding="utf-8") as f:
        f.write(f"{version}\n")

    task_template = os.path.join(skill_dir, "assets/templates/flow/tasks/TEMPLATE.md")
    task_template_target = os.path.join(tasks_dir, "TEMPLATE.md")
    if os.path.exists(task_template):
        shutil.copy2(task_template, task_template_target)

    # 4. project-flow 不安装、不修改任何 Hook；收工检查由主控 Agent 主动完成。

    # 5. Non-destructively update AGENTS.md
    agents_template_file = os.path.join(skill_dir, "assets/templates/AGENTS.md")
    with open(agents_template_file, "r", encoding="utf-8") as f:
        template_text = f.read()

    target_agents_file = os.path.join(target_dir, "AGENTS.md")
    sync_agents_runtime_contract(template_text, target_agents_file)

    # Ensure CLAUDE.md symlink
    claude_symlink = os.path.join(target_dir, "CLAUDE.md")
    if not os.path.exists(claude_symlink):
        try:
            os.symlink("AGENTS.md", claude_symlink)
        except Exception:
            pass

    # 6. Ensure flow base files exist
    base_flow_files = {
        "charter.md": os.path.join(skill_dir, "assets/templates/flow/charter.md"),
        "plan.md": os.path.join(skill_dir, "assets/templates/flow/plan.md"),
        "进展.md": os.path.join(skill_dir, "assets/templates/flow/进展.md"),
        "decisions.md": os.path.join(skill_dir, "assets/templates/flow/decisions.md"),
        "踩坑记录.md": os.path.join(skill_dir, "assets/templates/flow/踩坑记录.md"),
    }
    for name, src_path in base_flow_files.items():
        dst_path = os.path.join(flow_dir, name)
        if not os.path.exists(dst_path) and os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)

    # 7. Post-Update Technical Debt GC (自动更新后技术债回收)
    retire_technical_debt(target_dir, flow_dir, trash_dir)
    for item in moved:
        print(f"📦 [归档结构迁移] {item}")

if __name__ == "__main__":
    main()
