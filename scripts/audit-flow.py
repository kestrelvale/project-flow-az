#!/usr/bin/env python3
"""只读审计 project-flow 控制面，暴露遗留任务、旧格式与状态机违规。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

STATE_RE = re.compile(r"^\s*[-*]?\s*\[([ \-✓✕xX])\]\s+(.+)$")
TABLE_DONE_RE = re.compile(r"\|\s*(?:\[[✓xX]\]|✅\s*已完成)")
TABLE_TODO_RE = re.compile(r"\|\s*(?:\[[ ]\]|🔴\s*当前任务|⏳\s*(?:进行中|待启动))")
LEGACY_ACTIVE_RE = re.compile(r"(?:^#{1,6}\s*.*(?:当前任务|当前里程碑)|^\s*\|.*(?:当前任务|进行中|待启动))")


def classify_line(line: str):
    stripped = line.strip()
    match = STATE_RE.match(stripped)
    if match:
        state, title = match.groups()
        return state, title.strip(), "list"
    if "|" in stripped and TABLE_DONE_RE.search(stripped):
        return "✓", stripped, "table"
    if "|" in stripped and TABLE_TODO_RE.search(stripped):
        return " ", stripped, "table"
    return None


def audit(root: Path) -> dict:
    flow = root / "flow"
    result = {
        "root": str(root),
        "status": "ok",
        "errors": [],
        "warnings": [],
        "tasks": [],
        "legacy_plan": False,
        "files": {},
    }
    if not flow.is_dir():
        result["errors"].append("缺少 flow/ 控制面")
        result["status"] = "error"
        return result

    required = ["plan.md", "进展.md", "charter.md", "decisions.md", "踩坑记录.md"]
    for name in required:
        path = flow / name
        result["files"][name] = path.exists()
        if not path.exists():
            result["errors"].append(f"缺少 flow/{name}")

    plan = flow / "plan.md"
    if plan.exists():
        lines = plan.read_text(encoding="utf-8", errors="replace").splitlines()
        legacy_hits = 0
        for number, line in enumerate(lines, 1):
            classified = classify_line(line)
            if not classified:
                if LEGACY_ACTIVE_RE.search(line):
                    legacy_hits += 1
                continue
            state, title, kind = classified
            result["tasks"].append(
                {"line": number, "state": state, "title": title, "format": kind}
            )
            if state in "✓xX":
                result["errors"].append(
                    f"plan.md:{number} 活跃区存在已完成/废弃任务，应移入 flow/history 或 flow/trash"
                )
            if state == "-" and not ("验收" in title or "pending" in title.lower()):
                result["warnings"].append(f"plan.md:{number} [-] 项未明确标注待验收")

        if legacy_hits and not any(task["format"] == "table" for task in result["tasks"]):
            result["legacy_plan"] = True
            result["warnings"].append(
                "plan.md 仍是旧版表格/里程碑格式，未纳入四状态审计；应迁移为四状态看板"
            )

        if not result["tasks"] and not result["legacy_plan"]:
            result["warnings"].append(
                "plan.md 没有可审计任务；若本轮有用户任务，应先追加原子任务"
            )
        elif not any(task["state"] == " " for task in result["tasks"]):
            result["warnings"].append(
                "plan.md 没有 [ ] 当前焦点；若本轮有用户任务，应先追加原子任务"
            )

    progress = flow / "进展.md"
    if progress.exists():
        headings = [
            line
            for line in progress.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.startswith("## ")
        ]
        result["progress_entries"] = len(headings)
        if len(headings) > 5:
            result["warnings"].append(
                f"进展.md 有 {len(headings)} 条记录，超过建议的 5 条，应滚动归档"
            )

    history = flow / "history"
    trash = flow / "trash"
    result["history_files"] = (
        sum(1 for path in history.rglob("*") if path.is_file()) if history.exists() else 0
    )
    result["trash_files"] = (
        sum(1 for path in trash.rglob("*") if path.is_file()) if trash.exists() else 0
    )
    if not history.exists():
        result["warnings"].append("缺少 flow/history/，无法物理隔离已完成任务")
    if not trash.exists():
        result["warnings"].append("缺少 flow/trash/，无法隔离废弃方案")

    archive_dirs = {
        "history/plans": history / "plans",
        "history/tasks": history / "tasks",
        "history/progress": history / "progress",
        "trash/deprecated": trash / "deprecated",
        "trash/verification": trash / "verification",
        "gc/receipts": flow / "gc" / "receipts",
    }
    result["archive_counts"] = {}
    for name, path in archive_dirs.items():
        result["archive_counts"][name] = (
            sum(1 for item in path.rglob("*") if item.is_file()) if path.exists() else 0
        )
        if not path.exists():
            result["warnings"].append(f"缺少 flow/{name}/，归档与垃圾分区不规范")

    # 归档任务卡必须有对应 JSON 回执，否则无法回答“归档了没、为什么、什么证据”。
    archived_tickets = {
        path.stem
        for path in (history / "tasks").glob("*.md")
    } if (history / "tasks").is_dir() else set()
    receipt_tickets: set[str] = set()
    receipt_dir = flow / "gc" / "receipts"
    if receipt_dir.is_dir():
        for path in receipt_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("operation") == "task_archive" and data.get("ticket_id"):
                receipt_tickets.add(str(data["ticket_id"]))
    missing_receipts = sorted(ticket for ticket in archived_tickets if ticket not in receipt_tickets)
    result["archive_receipts"] = {
        "archived": len(archived_tickets),
        "with_receipt": len(archived_tickets) - len(missing_receipts),
    }
    if missing_receipts:
        shown = "、".join(missing_receipts[:5])
        more = f" 等 {len(missing_receipts)} 张" if len(missing_receipts) > 5 else ""
        result["warnings"].append(
            f"归档任务卡缺 JSON 回执：{shown}{more}；"
            f"请用 `flow-gc.py --task-archive` 归档以生成可追溯回执"
        )

    result["status"] = "error" if result["errors"] else ("warning" if result["warnings"] else "ok")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit(Path(args.root).resolve())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"project-flow 审计: {report['root']} [{report['status']}]")
        for key in ("errors", "warnings"):
            for item in report[key]:
                print(("FAIL: " if key == "errors" else "WARN: ") + item)
        print(
            f"任务 {len(report['tasks'])} 条；历史文件 {report['history_files']}；"
            f"废弃文件 {report['trash_files']}"
        )
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
