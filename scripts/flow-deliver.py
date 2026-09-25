#!/usr/bin/env python3
"""收工阶段生成完整四状态看板与交付验收卡。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

GATE_SCRIPT = Path(__file__).resolve().parent / "flow-gate.py"
DISTILL_SCRIPT = Path(__file__).resolve().parent / "flow-distill.py"
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

# decisions.md 是累积流水，实测 zhengjie-hrm 已达 164739 字节 / 1498 行 / 114 条，
# 而收工只要最后 3 条。全量读入等于每次交付都把整部决策史灌进上下文，
# 是压缩漂移的主要燃料之一。只读尾部即可。
MAX_DECISIONS_TAIL_BYTES = 32_000


def tail_lines(path: Path, limit_bytes: int) -> list[str]:
    """只读日志尾部的行，避免累积型文件被全量灌进上下文。"""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        start = max(0, size - limit_bytes)
        handle.seek(start)
        raw = handle.read()
    text = raw.decode("utf-8", errors="replace")
    if start > 0:
        text = text.split("\n", 1)[-1]  # 丢掉被字节切点截断的首行
    return text.splitlines()


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


def collect_specs(flow: Path, card: dict[str, str]) -> tuple[list[str], str]:
    """回收规格点/待办台账，返回（问题, 段落）。

    用户要求：汇报必须逐条回收规格点与 to-do 清单，否则任务中断后同一个需求点
    会被反复执行。台账存在但不合格（格式错 / 完成项无证据 = 假销账）时拒绝交付。
    """
    if not DISTILL_SCRIPT.is_file():
        return [], ""
    ticket = (card.get("ticket_id") or "").strip()
    result = subprocess.run(
        [
            sys.executable,
            str(DISTILL_SCRIPT),
            "spec",
            "--project",
            str(flow.parent),
            "--ticket",
            ticket,
        ],
        text=True,
        capture_output=True,
    )
    output = (result.stdout or "").strip()
    if not output or "无规格点台账" in output:
        return [], ""
    problems = [
        line.strip()[2:].strip() for line in output.splitlines() if line.strip().startswith("! ")
    ]
    rows = [line.strip() for line in output.splitlines() if line.strip().startswith("- [")]
    summary = [
        line.strip()
        for line in output.splitlines()
        if line.strip().startswith("- 规格点")
    ]
    if not rows and not problems:
        return [], ""
    lines = ["### ♻️ 规格点回收（中断后只做未回收项，已完成项不得重跑）", ""]
    lines.extend(summary)
    lines.extend(rows)
    pending = [row for row in rows if not row.startswith("- [x]")]
    if pending:
        lines.append(f"- 未回收 {len(pending)} 条：任务保持 `[-]` 待验收，不得标记完成。")
    else:
        lines.append("- 全部规格点已回收。")
    return problems, "\n".join(lines)


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
            # 旧实现把 plan.md 的占位文字原样带出，于是看板出现「- 无（…已归档 82 张）」
            # 这种自相矛盾（2026-09-25 实测，用户读到「看板宕机了」）。
            # 归档事实以磁盘为准：列真实计数与最近 3 张。
            archived = plan.parent / "history" / "tasks"
            cards = sorted(archived.glob("*.md")) if archived.is_dir() else []
            if cards:
                recent = "、".join(card.stem for card in cards[-3:])
                lines.append(f"- 已归档 {len(cards)} 张（flow/history/tasks/），最近：{recent}")
            else:
                lines.append("- 无")
        else:
            lines.append("- 无")
        lines.append("")

    lines.append("## 💡 本轮决策记录 (Decisions)")
    lines.extend(render_decisions(plan.parent / "decisions.md"))
    return "\n".join(lines).rstrip()


# 单条决策超长时截到这里；决策流水里存在整段贴入 memo 的条目。
MAX_DECISION_CHARS = 240


def render_decisions(decisions: Path) -> list[str]:
    """只输出**完整**决策条目（最后 3 条）。

    旧实现逐行过滤，把多行条目的续行也当成独立条目输出，于是看板出现半截
    `- [⚡ 自动决策] 统一登录夹具：` 和 ``- `resolve_feedback`…`` 这种残句
    （2026-09-25 实测，用户读到「汇报看板宕机」）。这里按「条目 = 起始行 + 其缩进续行」
    聚合，再压成一行；只保留带决策标签的条目。
    """
    if not decisions.is_file():
        return ["- 无"]
    entries: list[str] = []
    current: list[str] = []
    for line in decisions.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            if current:
                entries.append(" ".join(current))
            current = [stripped]
        elif current and (line.startswith((" ", "\t")) or stripped):
            # 续行（缩进或同段落的普通文本）并入当前条目，不单独成条
            current.append(stripped)
        elif current:
            entries.append(" ".join(current))
            current = []
    if current:
        entries.append(" ".join(current))
    recorded = [entry for entry in entries if any(marker in entry for marker in DECISION_MARKERS)]
    if not recorded:
        return ["- 无"]
    out: list[str] = []
    for entry in recorded[-3:]:
        entry = " ".join(entry.split())
        if len(entry) > MAX_DECISION_CHARS:
            entry = entry[:MAX_DECISION_CHARS].rstrip() + "…"
        out.append(entry)
    return out


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
    flow = locate_flow(args.card)
    spec_problems, spec_section = collect_specs(flow, card)
    if spec_problems:
        print("project-flow 拒绝交付：规格点台账不合格", file=sys.stderr)
        for problem in spec_problems:
            print(f"! {problem}", file=sys.stderr)
        print(
            ">>> 先修台账（flow/specs/<ticket>.md）再交付：完成项必须带证据，"
            "不得假销账。",
            file=sys.stderr,
        )
        return 1
    sections = [
        render_plan_sections(plan),
        render_work_summary(
            args.what,
            args.why,
            args.understanding,
            args.outputs,
            args.problem,
            args.next_step,
        ),
    ]
    if spec_section:
        sections.append(spec_section)
    sections.append(render(card, args.changed, args.evidence))
    block = "\n\n".join(sections)
    print(block)
    receipt, board = persist_delivery(flow, card, block)
    print()
    print(">>> 以上三段必须原样粘贴到回复，不得改写、不得只写摘要。")
    print(f">>> 交付回执：{receipt}")
    print(f">>> 看板副本：{board}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
