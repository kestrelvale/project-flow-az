#!/usr/bin/env python3
"""收工阶段生成完整四状态看板与交付验收卡。"""
from __future__ import annotations

import argparse
import importlib.util
import re
from pathlib import Path

GATE_SCRIPT = Path(__file__).resolve().parent / "flow-gate.py"
spec = importlib.util.spec_from_file_location("flow_gate", GATE_SCRIPT)
assert spec and spec.loader
FLOW_GATE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FLOW_GATE)
parse_card = FLOW_GATE.parse_card
STATE_RE = re.compile(r"^\s*[-*]\s*\[([ \-✓✕xX])\]\s+(.+?)\s*$")


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


def render_plan_sections(plan: Path) -> str:
    if not plan.is_file():
        return "### 📊 任务状态看板\n\n- plan.md 不存在"
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    heading = ""
    tasks: list[tuple[str, str]] = []
    for line in plan.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## "):
            if heading or tasks:
                sections.append((heading, tasks))
            heading = line[3:].strip()
            tasks = []
            continue
        match = STATE_RE.match(line)
        if match:
            tasks.append(match.groups())
    if heading or tasks:
        sections.append((heading, tasks))

    lines = ["### 📊 任务状态看板", ""]
    for section, section_tasks in sections:
        if not section_tasks:
            continue
        lines.append(f"## {section}")
        for state, title in section_tasks:
            lines.append(f"- [{state}] {title}")
        lines.append("")
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
    plan = args.plan or args.card.parent.parent / "plan.md"
    print(render_plan_sections(plan))
    print()
    print(
        render_work_summary(
            args.what,
            args.why,
            args.understanding,
            args.outputs,
            args.problem,
            args.next_step,
        )
    )
    print()
    print(render(parse_card(args.card), args.changed, args.evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
