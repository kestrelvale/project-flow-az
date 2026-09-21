#!/usr/bin/env python3
"""验证垃圾回收与进展日志滚动：只处理验证临时物，不处理任务归档。"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil

SAFE_TEMP_DIRS = {".tmp", "verification-tmp", "test-output", "test-results"}
MAX_PROGRESS_ENTRIES = 5
HISTORY_DIRS = ("plans", "tasks", "progress")
TRASH_DIRS = ("deprecated", "verification")


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}.{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"无法为 {path} 生成唯一回收路径")


def _rotate_progress(flow: Path, apply: bool) -> list[str]:
    progress = flow / "进展.md"
    if not progress.is_file():
        return []
    lines = progress.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    headings = [index for index, line in enumerate(lines) if line.startswith("## ")]
    if len(headings) <= MAX_PROGRESS_ENTRIES:
        return []
    cutoff = headings[MAX_PROGRESS_ENTRIES]
    old = "".join(lines[cutoff:])
    if not old.strip():
        return []
    destination = flow / "history" / "progress" / f"进展_{datetime.now():%Y%m}.md"
    message = f"进展.md: 滚动 {len(headings) - MAX_PROGRESS_ENTRIES} 条旧记录 -> {destination.relative_to(flow.parent)}"
    if apply:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("a", encoding="utf-8") as handle:
            handle.write(old)
        progress.write_text("".join(lines[:cutoff]).rstrip() + "\n", encoding="utf-8")
    return [message]


def gc(root: Path, apply: bool = False) -> dict:
    root = root.resolve()
    flow = root / "flow"
    result = {"root": str(root), "apply": apply, "moved": [], "rotated": []}
    if not flow.is_dir():
        return result

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for name in HISTORY_DIRS:
        (flow / "history" / name).mkdir(parents=True, exist_ok=True)
    for name in TRASH_DIRS:
        (flow / "trash" / name).mkdir(parents=True, exist_ok=True)

    destination_root = flow / "trash" / "verification" / stamp
    for entry in sorted(flow.iterdir()):
        if not entry.is_dir() or entry.name not in SAFE_TEMP_DIRS:
            continue
        destination = _unique_destination(destination_root / entry.name)
        result["moved"].append(f"{entry.relative_to(root)} -> {destination.relative_to(root)}")
        if apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(destination))

    result["rotated"] = _rotate_progress(flow, apply)
    if apply and (result["moved"] or result["rotated"]):
        receipt_dir = flow / "gc" / "receipts"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = receipt_dir / f"{datetime.now():%Y%m%d-%H%M%S}.json"
        receipt.write_text(
            json.dumps(
                {
                    "operation": "verification_gc_and_log_rotation",
                    "root": str(root),
                    "moved": result["moved"],
                    "rotated": result["rotated"],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result["receipt"] = str(receipt.relative_to(root))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = gc(Path(args.root), args.apply)
    mode = "已回收" if args.apply else "待回收"
    print(f"project-flow GC [{mode}]: {result['root']}")
    for item in result["moved"] + result["rotated"]:
        print(f"- {item}")
    if not result["moved"] and not result["rotated"]:
        print("- 无可回收验证临时物")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
