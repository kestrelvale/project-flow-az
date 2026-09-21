#!/usr/bin/env python3
"""project-flow 开工入口：定位项目、按需热同步、执行只读审计。"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = SKILL_DIR / "scripts" / "sync-project.py"
AUDIT_SCRIPT = SKILL_DIR / "scripts" / "audit-flow.py"
GC_SCRIPT = SKILL_DIR / "scripts" / "flow-gc.py"
GATE_SCRIPT = SKILL_DIR / "scripts" / "flow-gate.py"
BUDGET_SCRIPT = SKILL_DIR / "scripts" / "flow-budget.py"
PLAN_TASK_RE = re.compile(r"^\s*[-*]\s*\[([ \-✕xX])\]\s+(.+?)\s*$")
CARD_KEYS = (
    "ticket_id",
    "goal",
    "objective",
    "mode",
    "method",
    "write_whitelist",
    "verify_command",
    "acceptance",
    "next_agent",
    "next_action",
)
FOCUS_HEADING_MARKERS = ("当前聚焦", "当前任务", "施工队列")


def find_project_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "flow" / "plan.md").is_file():
            return candidate
    return None


def read_version(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_card(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        if key.strip() in CARD_KEYS:
            values[key.strip()] = value.strip()
    return values


def card_goal(card: dict[str, str]) -> str:
    """新卡用 goal，旧卡沿用 objective。"""
    return card.get("goal", "") or card.get("objective", "")


def parse_plan_sections(plan: Path) -> list[tuple[str, list[tuple[str, str]]]]:
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    current_heading = ""
    current_tasks: list[tuple[str, str]] = []
    for line in plan.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## "):
            if current_heading or current_tasks:
                sections.append((current_heading, current_tasks))
            current_heading = line[3:].strip()
            current_tasks = []
            continue
        match = PLAN_TASK_RE.match(line)
        if match:
            state, title = match.groups()
            current_tasks.append((state, title))
    if current_heading or current_tasks:
        sections.append((current_heading, current_tasks))
    return sections


def read_active_tasks(plan: Path) -> list[tuple[str, str]]:
    sections = parse_plan_sections(plan)
    focused = [
        (heading, tasks)
        for heading, tasks in sections
        if any(marker in heading for marker in FOCUS_HEADING_MARKERS)
    ]
    if focused:
        return list(
            dict.fromkeys(
                task
                for _, tasks in focused
                for task in tasks
                if task[0] in {" ", "✕", "x", "X"}
            )
        )
    if sections:
        first = list(dict.fromkeys(sections[0][1]))
        pending = [task for task in first if task[0] == " "]
        return pending
    return []


def read_unmanaged_tasks(plan: Path, active_tasks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    sections = parse_plan_sections(plan)
    focused = [
        (heading, tasks)
        for heading, tasks in sections
        if any(marker in heading for marker in FOCUS_HEADING_MARKERS)
    ]
    managed_sections = focused if focused else sections[:1]
    managed = {task for _, tasks in managed_sections for task in tasks}
    leftovers = [task for _, tasks in sections for task in tasks if task not in managed]
    return list(dict.fromkeys(leftovers))


def read_pending_tasks(plan: Path) -> list[str]:
    return [
        title
        for _, tasks in parse_plan_sections(plan)
        for state, title in tasks
        if state == "-"
    ]


def read_completed_tasks(plan: Path) -> list[str]:
    return [
        title
        for _, tasks in parse_plan_sections(plan)
        for state, title in tasks
        if state in {"✓", "x", "X"}
    ]


# plan.md 里这些章节属于“已终结”，其内容应物理归档，不得长期驻留活跃控制面。
ARCHIVED_HEADING_RE = re.compile(r"归档|Archived|已完成|已废弃|废弃任务")


def measure_plan_bloat(plan: Path) -> list[str]:
    """暴露 plan.md 里堆积的已归档/已废弃内容。

    历史实现只在归档区写裸 `-` 列表项，状态正则识别不到，于是这些
    已终结内容会静静堆在活跃控制面里，开工时反复注入上下文造成漂移。
    这里按章节体积直接度量，不依赖状态标记。
    """
    if not plan.is_file():
        return []
    total = len(plan.read_text(encoding="utf-8", errors="replace"))
    if total == 0:
        return []
    reports: list[str] = []
    current = ""
    size = 0
    sections: list[tuple[str, int]] = []

    def flush() -> None:
        if current and size:
            sections.append((current, size))

    for line in plan.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True):
        if line.startswith("## "):
            flush()
            current = line[3:].strip()
            size = len(line)
            continue
        size += len(line)
    flush()

    for title, section_size in sections:
        if not ARCHIVED_HEADING_RE.search(title):
            continue
        share = section_size * 100 // total
        if share >= 25:
            reports.append(
                f"plan.md「{title}」占全文 {share}%（{section_size}/{total} 字节）："
                f"已终结内容应物理剪切到 flow/history/，活跃控制面只留指针。"
            )
    return reports


def card_is_linked(card: dict[str, str], active_tasks: list[tuple[str, str]]) -> bool:
    ticket = card.get("ticket_id", "")
    objective = card_goal(card)
    for _, title in active_tasks:
        if ticket and ticket in title:
            return True
        if objective and objective in title:
            return True
    return False


def text_overlap(left: str, right: str) -> bool:
    fragments = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{3,}", left))
    return any(fragment in right for fragment in fragments)


def find_orphan_cards(
    cards: list[tuple[Path, dict[str, str]]],
    active_tasks: list[tuple[str, str]],
) -> list[str]:
    """任务卡存在但已不在活跃区，属于长期滞留的回收债务。"""
    return sorted(
        {
            card.get("ticket_id") or path.name
            for path, card in cards
            if card.get("mode") in {"plan", "execute", "review"}
            and not card_is_linked(card, active_tasks)
        }
    )


def route_hint(
    active_tasks: list[tuple[str, str]],
    cards: list[tuple[Path, dict[str, str]]],
    unmanaged_tasks: list[tuple[str, str]],
    intent: str = "",
) -> list[str]:
    if not cards:
        hints = [
            "未发现任务卡：先按 SDD 在 flow/plan.md 登记 [ ] 原子任务，并创建 flow/tasks/<ticket>.md。",
            "在任务卡通过对应阶段门禁前，不得修改业务代码。",
        ]
        if active_tasks:
            hints.append(
                "路由阻塞：" + "、".join(title for _, title in active_tasks) + " 尚无绑定任务卡。"
            )
        return hints

    plan_cards = [
        (path, card)
        for path, card in cards
        if card.get("mode") == "plan" and card_is_linked(card, active_tasks)
    ]
    execute_cards = [
        (path, card)
        for path, card in cards
        if card.get("mode") == "execute" and card_is_linked(card, active_tasks)
    ]
    handoff_cards = [(path, card) for path, card in cards if card.get("mode") == "handoff"]
    review_cards = [(path, card) for path, card in cards if card.get("mode") == "review"]
    hints: list[str] = []

    if plan_cards:
        hints.append(
            "Plan 路由：" + "、".join(card.get("ticket_id", path.name) for path, card in plan_cards)
            + "；项目初期阶段：只读执行 Plan / Goal / SDD 规划门，禁止修改业务代码。"
        )
    if execute_cards:
        hints.append(
            "Execute 路由：" + "、".join(card.get("ticket_id", path.name) for path, card in execute_cards)
            + "；实现阶段：先写失败测试再最小实现 (TDD)，留下 Exit 0 证据。"
        )
    if review_cards:
        hints.append(
            "Review 路由：" + "、".join(card.get("ticket_id", path.name) for path, card in review_cards)
            + "；验收阶段：用 ATDD 可执行断言验收，不重复开工。"
        )
    if handoff_cards:
        hints.append(
            "Handoff 路由：" + "、".join(card.get("ticket_id", path.name) for path, card in handoff_cards)
            + "；收尾阶段：用 BDD 的 Given-When-Then 交接下一步，不进入 Execute 队列。"
        )

    stale_cards = find_orphan_cards(cards, active_tasks)
    if stale_cards:
        hints.append(
            "静默任务卡：" + "、".join(stale_cards)
            + "；不在活跃区，按 [-] 待验收或历史卡处理，禁止重复执行。"
        )

    unbound = [
        title
        for _, title in active_tasks
        if not any(card_is_linked(card, [(" ", title)]) for _, card in cards)
    ]
    if unbound:
        hints.append("路由阻塞：" + "、".join(unbound) + " 尚无绑定任务卡，必须先补 SDD 卡。")

    if intent:
        matched = []
        for path, card in cards:
            ticket = card.get("ticket_id", "")
            objective = card_goal(card)
            if (ticket and ticket in intent) or (objective and intent in objective) or any(
                text_overlap(intent, title)
                for _, title in active_tasks
                if ticket and card_is_linked(card, [(" ", title)])
            ):
                matched.append(ticket or objective or path.stem)
        if matched:
            hints.append("本轮意图已绑定任务卡：" + "、".join(matched))
        else:
            hints.append(
                f"本轮意图“{intent}”未登记：先按 SDD 写入 flow/plan.md，并创建或更新任务卡，再改业务代码。"
            )
    if unmanaged_tasks:
        hints.append(
            "未纳管遗留：" + "、".join(title for _, title in unmanaged_tasks)
            + "；仅暴露债务，不进入本轮施工队列。"
        )
    return hints


def render_start_status(
    active_tasks: list[tuple[str, str]],
    cards: list[tuple[Path, dict[str, str]]],
    unmanaged_tasks: list[tuple[str, str]],
    pending_tasks: list[str],
    completed_tasks: list[str],
    orphan_cards: list[str],
    bloat_reports: list[str],
) -> list[str]:
    status = ["### project-flow 开工状态", "", "## 🎯 当前聚焦待办 (P0)"]
    pending = [(state, title) for state, title in active_tasks if state in {" ", "✕", "x", "X"}]
    if pending:
        for state, title in pending:
            status.append(f"- [{state}] {title}")
    else:
        status.append("- [ ] 本轮尚未登记原子任务")

    status.extend(["", "## 🚧 路由阻塞"])
    blockers = [
        title
        for _, title in active_tasks
        if not any(card_is_linked(card, [(" ", title)]) for _, card in cards)
    ]
    if blockers:
        status.extend(f"- 尚无绑定任务卡：{title}" for title in blockers)
    else:
        status.append("- 无")

    status.extend(["", "## 🧹 未纳管遗留"])
    if unmanaged_tasks:
        status.extend(f"- {title}" for _, title in unmanaged_tasks)
    else:
        status.append("- 无")

    status.extend(["", "## 🧾 只读状态计数"])
    status.append(f"- 待验收：{len(pending_tasks)}")
    if pending_tasks:
        status.extend(f"  - {title}" for title in pending_tasks)

    decision_tasks = [
        title
        for _, title in active_tasks
        if any(keyword in title for keyword in ("待用户确认", "需用户确认", "待决策", "人工决策"))
    ]
    status.extend(["", "## ⚠️ 待人工决策"])
    if decision_tasks:
        status.extend(f"- {title}" for title in decision_tasks)
    else:
        status.append("- 无")

    status.extend(["", "## ♻️ 回收建议"])
    if pending_tasks:
        status.append(
            f"- 待验收积压 {len(pending_tasks)} 项：请逐项确认后归档，或退回修复；不得自动标记通过。"
        )
    if completed_tasks:
        status.append(
            f"- 活跃区残留已完成项 {len(completed_tasks)} 项：应移入 flow/history/。"
        )
    # 孤儿卡：任务卡存在但已不在活跃区，长期滞留 flow/tasks/ 会让后续开工
    # 反复看到旧卡而互相干扰，属于必须暴露的回收债务。
    if orphan_cards:
        status.append(
            f"- 孤儿任务卡 {len(orphan_cards)} 张：不在活跃区却仍留在 flow/tasks/，"
            f"应确认后归档到 flow/history/tasks/ 或退回活跃区。"
        )
        status.extend(f"  - {card_id}" for card_id in orphan_cards)
    if bloat_reports:
        status.extend(f"- {report}" for report in bloat_reports)
    if not pending_tasks and not completed_tasks and not orphan_cards and not bloat_reports:
        status.append("- 无")
    return status


def intent_matches(
    intent: str,
    active_tasks: list[tuple[str, str]],
    cards: list[tuple[Path, dict[str, str]]],
) -> bool:
    for path, card in cards:
        ticket = card.get("ticket_id", "")
        objective = card_goal(card)
        if (ticket and ticket in intent) or (objective and intent in objective):
            return True
        if any(
            text_overlap(intent, title)
            for _, title in active_tasks
            if ticket and card_is_linked(card, [(" ", title)])
        ):
            return True
    return False


def render_sdd_gate(intent: str, active_tasks: list[tuple[str, str]], cards: list[tuple[Path, dict[str, str]]]) -> list[str]:
    if not intent:
        return []
    if intent_matches(intent, active_tasks, cards):
        return []
    return [
        "### project-flow SDD 登记门",
        "",
        f"- 本轮意图：{intent}",
        "- 状态：未绑定活跃任务卡，禁止进入业务实现。",
        "- 下一步：先补齐以下最小规格，再创建 `flow/tasks/<ticket>.md`：",
        "  - 目标：一句话描述可观察结果；",
        "  - 输入：触发方式、字段、有效和无效边界；",
        "  - 输出：返回值、界面状态、文件或日志变化；",
        "  - 写入白名单：本轮允许修改的路径；",
        "  - TDD：先留下一个能因缺陷而失败的检查；",
        "  - ATDD：可执行的接口、端到端或脚本断言；",
        "  - BDD：Given-When-Then 人工验收场景。",
        "- 门禁命令：`python3 ~/.codex/skills/project-flow-az/scripts/flow-gate.py flow/tasks/<ticket>.md --phase plan`",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("start", nargs="?", default=".")
    parser.add_argument("--intent", default="", help="本轮用户任务的简短摘要")
    parser.add_argument("--thread-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--skip-budget", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    project_root = find_project_root(Path(args.start))
    if project_root is None:
        print("project-flow: 当前路径及父目录没有 flow/plan.md，未接管")
        print("- 当前工作目录不属于任何已接入项目。")
        print("- 请切换到项目根目录后重新运行 flow-boot.py。")
        return 1

    global_version = read_version(SKILL_DIR / "VERSION")
    project_version = read_version(project_root / "flow" / "规范" / "VERSION")
    sync = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), str(SKILL_DIR), str(project_root)],
        text=True,
        capture_output=True,
    )
    if sync.returncode != 0:
        print(sync.stdout, end="")
        print(sync.stderr, end="", file=sys.stderr)
        print(f"project-flow: 同步失败，继续执行只读审计 [{project_version or '缺失'} -> {global_version}]")
    elif project_version != global_version:
        print(f"project-flow: 已热同步 [{project_version or '缺失'} -> {global_version}]")
    sys.stdout.flush()

    audit = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), str(project_root)],
        text=True,
    )
    gc = subprocess.run(
        [sys.executable, str(GC_SCRIPT), str(project_root), "--apply"],
        text=True,
    )
    plan = project_root / "flow" / "plan.md"
    active_tasks = read_active_tasks(plan)
    unmanaged_tasks = read_unmanaged_tasks(plan, active_tasks)
    pending_tasks = read_pending_tasks(plan)
    completed_tasks = read_completed_tasks(plan)
    gate_code = 0
    cards: list[tuple[Path, dict[str, str]]] = []
    tasks_dir = project_root / "flow" / "tasks"
    if tasks_dir.is_dir():
        for card in sorted(tasks_dir.rglob("*.md")):
            if card.name == "TEMPLATE.md" or "archive" in card.relative_to(tasks_dir).parts:
                continue
            values = read_card(card)
            cards.append((card, values))
            mode = values.get("mode", "plan")
            phase = mode if mode in {"plan", "execute", "review", "handoff"} else "plan"
            gate = subprocess.run(
                [sys.executable, str(GATE_SCRIPT), str(card), "--phase", phase],
                text=True,
            )
            gate_code = max(gate_code, gate.returncode)

    orphan_cards = find_orphan_cards(cards, active_tasks)
    bloat_reports = measure_plan_bloat(plan)
    print(
        "\n".join(
            render_start_status(
                active_tasks,
                cards,
                unmanaged_tasks,
                pending_tasks,
                completed_tasks,
                orphan_cards,
                bloat_reports,
            )
        )
    )
    print("\nproject-flow 接管路由")
    print(f"- 项目: {project_root}")
    if active_tasks:
        for state, title in active_tasks:
            print(f"- 活跃 [{state}] {title}")
    else:
        print("- 活跃 [ ]: 无；本轮必须先登记原子任务，再开始业务改动")
    if cards:
        for path, card in cards:
            status = "已绑定" if card_is_linked(card, active_tasks) else "未绑定活跃区"
            card_id = card.get("ticket_id") or "(无 ticket_id)"
            print(
                f"- 任务卡 [{card.get('mode', 'unknown')}] {card_id}"
                f" | {status} | {card_goal(card) or '缺少 goal/objective'}"
                f" | next={card.get('next_action', '缺少 next_action')} -> {path}"
            )
    else:
        print("- 任务卡: 无")
    if args.intent:
        print(f"- 本轮意图: {args.intent}")
    for hint in route_hint(active_tasks, cards, unmanaged_tasks, args.intent):
        print(f"- 路由: {hint}")
    sdd_gate = render_sdd_gate(args.intent, active_tasks, cards)
    if sdd_gate:
        print("\n" + "\n".join(sdd_gate))
    budget_code = 0
    if not args.skip_budget:
        budget = subprocess.run(
            [
                sys.executable,
                str(BUDGET_SCRIPT),
                "--intent",
                args.intent or "继续当前 project-flow 活跃任务",
                *(["--thread-id", args.thread_id] if args.thread_id else []),
            ],
            text=True,
        )
        budget_code = budget.returncode
    return max(audit.returncode, gc.returncode, gate_code, budget_code)


if __name__ == "__main__":
    raise SystemExit(main())
