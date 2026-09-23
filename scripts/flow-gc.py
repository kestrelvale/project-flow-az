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
# 只按条数分页不够：单条日志可达 1.5KB，5 条也可能几十 KB。
# 再加字节上限，超限即滚动，避免历史把开工上下文撑爆。
# 实测：o2o 进展.md 涨到 52KB / 41 条，每次开工全量灌进上下文导致熔断。
# 阈值按“开工可承受”设定，而不是按条数。
MAX_PROGRESS_BYTES = 12_000
KEEP_PROGRESS_BYTES = 6_000
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
    # 条目标题可能是 `## ` 或 `### `：模板用 `## `，但历史项目实际写成
    # `### `，旧实现只认 `## `，导致 40 条日志一条都没滚动。
    headings = [
        index
        for index, line in enumerate(lines)
        if line.startswith("## ") or line.startswith("### ")
    ]
    total_bytes = len("".join(lines))
    if len(headings) <= MAX_PROGRESS_ENTRIES and total_bytes <= MAX_PROGRESS_BYTES:
        return []

    if not headings:
        return []

    # 从最旧一端开始裁：保留最近若干条，直到保留部分进入 KEEP_PROGRESS_BYTES。
    # 同时满足“条数不超上限、字节不超上限”两个约束，取两者中更靠后的切点。
    cutoff = headings[-1]
    for index in headings[1:]:
        if len("".join(lines[index:])) <= KEEP_PROGRESS_BYTES:
            cutoff = index
            break
    if len(headings) > MAX_PROGRESS_ENTRIES:
        cutoff = min(cutoff, headings[MAX_PROGRESS_ENTRIES])

    old = "".join(lines[cutoff:])
    if not old.strip():
        return []
    destination = flow / "history" / "progress" / f"进展_{datetime.now():%Y%m}.md"
    moved = sum(1 for index in headings if index >= cutoff)
    message = f"进展.md: 滚动 {moved} 条旧记录 -> {destination.relative_to(flow.parent)}"
    # 单条本身就可能超过保留阈值，此时只保证最新一条留在活跃区。
    # 注意：交接棒**不再有字节上限**（v4.15.16）——这里只提示「记录太长、考虑滚动」，
    # 不再要求作者压缩内容；防复述由 flow-distill 的照抄检测承担。
    if len("".join(lines[cutoff:]).encode("utf-8")) > MAX_PROGRESS_BYTES:
        message += "（最新一条仍超阈值，请按交接规范精简）"
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


TASK_ARCHIVE_DIR = ("history", "tasks")


def archive_task(
    root: Path,
    ticket: str,
    *,
    reason: str,
    evidence: str,
    apply: bool = False,
) -> dict:
    """把已验收任务卡归档到 flow/history/tasks/ 并写标准回执。

    旧实现靠手写 Markdown 回执，格式各异且机器读不了，导致“这个任务归档了没、
    为什么归档、有什么证据”三问答不上来。这里统一成 JSON 回执。
    """
    root = root.resolve()
    flow = root / "flow"
    source = flow / "tasks" / f"{ticket}.md"
    destination = flow.joinpath(*TASK_ARCHIVE_DIR) / f"{ticket}.md"
    result = {
        "root": str(root),
        "ticket_id": ticket,
        "from": str(source.relative_to(root)),
        "to": str(destination.relative_to(root)),
        "reason": reason,
        "evidence": evidence,
        "apply": apply,
    }
    if not source.is_file():
        result["error"] = f"任务卡不存在：{source.relative_to(root)}"
        return result
    if not evidence.strip():
        result["error"] = "缺少验收证据：归档必须绑定 evidence"
        return result
    if apply:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        receipt_dir = flow / "gc" / "receipts"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = receipt_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{ticket}.json"
        payload = {
            "operation": "task_archive",
            "ticket_id": ticket,
            "from": result["from"],
            "to": result["to"],
            "reason": reason,
            "evidence": evidence,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        receipt.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        result["receipt"] = str(receipt.relative_to(root))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--task-archive", metavar="TICKET", default="")
    parser.add_argument("--reason", default="user_accepted")
    parser.add_argument("--evidence", default="")
    args = parser.parse_args()

    if args.task_archive:
        archived = archive_task(
            Path(args.root),
            args.task_archive,
            reason=args.reason,
            evidence=args.evidence,
            apply=args.apply,
        )
        if archived.get("error"):
            print(f"project-flow 归档失败：{archived['error']}")
            return 1
        action = "已归档" if args.apply else "待归档"
        print(f"project-flow Task Archive [{action}]: {archived['ticket_id']}")
        print(f"- {archived['from']} -> {archived['to']}")
        print(f"- 原因：{archived['reason']}；证据：{archived['evidence']}")
        if archived.get("receipt"):
            print(f"- 回执：{archived['receipt']}")
        return 0

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
