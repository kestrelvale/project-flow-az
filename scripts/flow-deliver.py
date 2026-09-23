#!/usr/bin/env python3
"""收工阶段生成完整四状态看板与交付验收卡。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

GATE_SCRIPT = Path(__file__).resolve().parent / "flow-gate.py"
spec = importlib.util.spec_from_file_location("flow_gate", GATE_SCRIPT)
assert spec and spec.loader
FLOW_GATE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FLOW_GATE)
parse_card = FLOW_GATE.parse_card
STATE_RE = re.compile(r"^\s*[-*]\s*\[([ \-✓✕xX])\]\s+(.+?)\s*$")

# 交付回执目录与人工可读看板副本。
# stdout 只活在工具结果里：实测 2026-09-22 的 o2o 会话里 flow-deliver.py
# 跑了 7 次，用户可见回复里 0 次出现看板——模型漏贴就彻底丢失。
# 落盘后 flow-boot.py 才有依据对“已进待验收却从未交付”的债务开火。
DELIVERIES_DIR = "deliveries"
BOARD_FILE = "看板.md"


def locate_flow(card: Path) -> Path:
    """任务卡所属的 flow/ 目录，回执与看板都写在这里。"""
    return locate_plan(card).parent


def persist_delivery(flow: Path, card: dict[str, str], block: str) -> tuple[Path, Path]:
    """把收工汇报落盘：一份 JSON 回执 + 一份人类可读看板副本。"""
    ticket = (card.get("ticket_id") or "").strip() or "unknown"
    receipt_dir = flow / DELIVERIES_DIR
    receipt_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now()
    board = flow / BOARD_FILE
    board.write_text(block.rstrip() + "\n", encoding="utf-8")
    receipt = receipt_dir / f"{stamp:%Y%m%d-%H%M%S}-{ticket}.json"
    receipt.write_text(
        json.dumps(
            {
                "operation": "delivery",
                "ticket_id": ticket,
                "delivered_at": stamp.isoformat(timespec="seconds"),
                "board_copy": str(board.name),
                "chars": len(block),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt, board


def locate_plan(card: Path) -> Path:
    """向上找到 flow/plan.md。

    归档卡位于 flow/history/tasks/，用 card.parent.parent 会错算成
    flow/history/plan.md，导致收工看板退化成“plan.md 不存在”。
    """
    for parent in card.resolve().parents:
        if parent.name == "flow" and (parent / "plan.md").is_file():
            return parent / "plan.md"
        candidate = parent / "flow" / "plan.md"
        if candidate.is_file():
            return candidate
    return card.parent.parent / "plan.md"


def render(card: dict[str, str], changed: str, evidence: str) -> str:
    ticket = card.get("ticket_id", "(无 ticket_id)")
    objective = card.get("goal", "") or card.get("objective", "") or "缺少 goal/objective"
    verify = card.get("verify_command", "缺少 verify_command")
    acceptance = card.get("acceptance", "缺少 acceptance")
    files = changed or "未提供；不得以 write_whitelist 冒充实际改动"
    boundary = card.get("write_whitelist", "缺少 write_whitelist")
    proof = evidence or card.get("evidence", "缺少 evidence")
    return "\n".join(
        [
            "### project-flow 交付验收卡",
            "",
            f"- 任务：{ticket}",
            f"- 目标：{objective}",
            f"- 实际改动：{files}",
            f"- 允许边界：{boundary}",
            f"- 自动验证：`{verify}`",
            f"- 验证证据：{proof}",
            f"- 人工验收（Given-When-Then）：{acceptance}",
            "- 状态：[-] 待人工验收；用户确认前不得重复执行。",
        ]
    )


def render_work_summary(
    what: str,
    why: str,
    understanding: str,
    outputs: str,
    problem: str,
    next_step: str,
) -> str:
    lines = [
        "### 📝 本轮工作汇报",
        "",
        f"- 做了什么：{what or '缺少 --what'}",
        f"- 为什么这么做：{why or '缺少 --why'}",
        f"- 怎么理解：{understanding or '缺少 --understanding'}",
        f"- 产出路径：{outputs or '缺少 --outputs'}",
    ]
    if problem:
        lines.append(f"- 问题 → 怎么解决：{problem}")
    lines.append(f"- 下一步：{next_step or '缺少 --next-step'}")
    return "\n".join(lines)


# 收工看板是固定四分区契约：标题永远存在，空分区显式写“无”。
# 早期实现直接照抄各项目 plan.md 的自定义标题，导致标题随项目漂移、
# 任务全部归档后整块看板变空——这正是汇报不稳定的根因。
BOARD_SECTIONS = (
    ("## 🎯 当前聚焦待办 (P0)", (" ", "✕", "x", "X")),
    ("## ⏳ 待人工验收 (Pending Verification)", ("-",)),
    ("## 📦 已完结归档 (Archived in flow/history/)", ("✓",)),
)

# 看板只收真正的决策条目，避免把 decisions.md 的章节结构当决策。
DECISION_MARKERS = ("自动决策", "人工决策", "决策：", "决策:", "[⚡", "[⚠️")


def render_plan_sections(plan: Path) -> str:
    tasks: list[tuple[str, str]] = []
    if plan.is_file():
        for line in plan.read_text(encoding="utf-8", errors="replace").splitlines():
            match = STATE_RE.match(line)
            if match:
                tasks.append(match.groups())

    lines = ["### 📊 任务状态看板", ""]
    for heading, states in BOARD_SECTIONS:
        lines.append(heading)
        matched = [f"- [{state}] {title}" for state, title in tasks if state in states]
        if matched:
            lines.extend(matched)
        elif states == ("✓",):
            archived = plan.parent / "history" / "tasks"
            count = len(list(archived.glob("*.md"))) if archived.is_dir() else 0
            lines.append(f"- 无（flow/history/tasks/ 已归档 {count} 张任务卡）")
        else:
            lines.append("- 无")
        lines.append("")

    lines.append("## 💡 本轮决策记录 (Decisions)")
    decisions = plan.parent / "decisions.md"
    recorded: list[str] = []
    if decisions.is_file():
        for line in decisions.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped.startswith(("- ", "* ")):
                continue
            # decisions.md 是累计流水，含“背景/影响范围”等章节结构噪音；
            # 看板只收带决策标签的真实条目。
            if any(marker in stripped for marker in DECISION_MARKERS):
                recorded.append(stripped)
    if recorded:
        lines.extend(recorded[-3:])
    else:
        lines.append("- 无")
    return "\n".join(lines).rstrip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("card", type=Path)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--changed", default="")
    parser.add_argument("--evidence", default="")
    parser.add_argument("--what", default="")
    parser.add_argument("--why", default="")
    parser.add_argument("--understanding", default="")
    parser.add_argument("--outputs", default="")
    parser.add_argument("--problem", default="")
    parser.add_argument("--next-step", default="")
    args = parser.parse_args()
    plan = args.plan or locate_plan(args.card)
    card = parse_card(args.card)
    block = "\n\n".join(
        [
            render_plan_sections(plan),
            render_work_summary(
                args.what,
                args.why,
                args.understanding,
                args.outputs,
                args.problem,
                args.next_step,
            ),
            render(card, args.changed, args.evidence),
        ]
    )
    print(block)
    receipt, board = persist_delivery(locate_flow(args.card), card, block)
    print()
    print(">>> 以上三段必须原样粘贴到回复，不得改写、不得只写摘要。")
    print(f">>> 交付回执：{receipt}")
    print(f">>> 看板副本：{board}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
