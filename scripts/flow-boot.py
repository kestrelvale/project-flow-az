#!/usr/bin/env python3
"""project-flow 开工入口：定位项目、按需热同步、执行只读审计。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = SKILL_DIR / "scripts" / "sync-project.py"
AUDIT_SCRIPT = SKILL_DIR / "scripts" / "audit-flow.py"
GC_SCRIPT = SKILL_DIR / "scripts" / "flow-gc.py"
GATE_SCRIPT = SKILL_DIR / "scripts" / "flow-gate.py"
BUDGET_SCRIPT = SKILL_DIR / "scripts" / "flow-budget.py"

_GATE_SPEC = importlib.util.spec_from_file_location("flow_gate", GATE_SCRIPT)
assert _GATE_SPEC and _GATE_SPEC.loader
FLOW_GATE = importlib.util.module_from_spec(_GATE_SPEC)
_GATE_SPEC.loader.exec_module(FLOW_GATE)

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
    "depends_on",
    "next_agent",
    "next_action",
)
FOCUS_HEADING_MARKERS = ("当前聚焦", "当前任务", "施工队列")
CLAIMS_DIR = "claims"
CLAIM_TTL_HOURS = 12


def load_claims(flow: Path) -> dict[str, dict[str, object]]:
    """读取 flow/claims/ 下的任务认领记录。"""
    claims: dict[str, dict[str, object]] = {}
    directory = flow / CLAIMS_DIR
    if not directory.is_dir():
        return claims
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ticket = str(data.get("ticket_id") or path.stem)
        claims[ticket] = data
    return claims


def claim_is_stale(claim: dict[str, object], now: float) -> bool:
    try:
        claimed_at = float(claim.get("claimed_at") or 0)
    except (TypeError, ValueError):
        return True
    return (now - claimed_at) > CLAIM_TTL_HOURS * 3600


def write_claim(flow: Path, ticket: str, thread_id: str, now: float) -> None:
    directory = flow / CLAIMS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{ticket}.json").write_text(
        json.dumps(
            {"ticket_id": ticket, "thread_id": thread_id, "claimed_at": now},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def claim_active_tasks(
    flow: Path,
    cards: list[tuple[Path, dict[str, str]]],
    active_tasks: list[tuple[str, str]],
    thread_id: str,
) -> list[str]:
    """让当前会话认领本轮活跃任务，阻止另一个会话抢同一张卡。

    多端并行时两个 Codex 会话可能同时读到同一批活跃任务；没有认领记录就会
    各自施工同一张卡，表现为任务串线。认领带过期时间，避免会话崩溃后死锁。
    """
    if not thread_id:
        return []
    now = time.time()
    claims = load_claims(flow)
    conflicts: list[str] = []
    owned: list[str] = []
    for path, card in cards:
        if card.get("mode") not in {"execute", "plan"}:
            continue
        if not card_is_linked(card, active_tasks):
            continue
        ticket = card.get("ticket_id") or path.stem
        existing = claims.get(ticket)
        if existing:
            owner = str(existing.get("thread_id") or "")
            if owner and owner != thread_id and not claim_is_stale(existing, now):
                conflicts.append(
                    f"{ticket} 已由会话 {owner[:8]} 认领，本会话不得并行施工；"
                    f"等待其交付或超过 {CLAIM_TTL_HOURS} 小时过期后接管。"
                )
                continue
        owned.append(ticket)
        write_claim(flow, ticket, thread_id, now)
    if owned:
        conflicts.append(
            f"本会话已认领：{'、'.join(owned)}；其他会话开工时将看到占用标记。"
        )
    return conflicts


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
    """复用 flow-gate 的解析器，避免多份实现漂移。

    自研的第二份解析器不认 YAML 块标量，把 `write_whitelist: |` 读成 `|`，
    进而让并行冲突检测产生 `| ↔ |` 假阳性。
    """
    return {
        key: value
        for key, value in FLOW_GATE.parse_card(path).items()
        if key in CARD_KEYS
    }


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


def split_paths(raw: str) -> list[str]:
    return [
        item.strip().rstrip("/")
        for item in re.split(r"[,，;；\n]", raw)
        if item.strip() and not is_control_plane(item.strip())
    ]


def is_control_plane(path: str) -> bool:
    """编排器独占的控制面路径不参与并行冲突判定。

    `flow/` 与 `docs/reviews/` 由主控统一写入，子 Agent 本就不该碰；
    把它们算作冲突会让每张卡互相“重叠”，淹没真正会互相覆盖的源码。
    """
    normalized = path.strip().lstrip("./")
    return normalized.startswith(("flow/", "docs/reviews/")) or normalized in {"flow", "docs/reviews"}


def paths_overlap(left: str, right: str) -> bool:
    """判断两个写入白名单条目是否可能落到同一文件或目录。"""
    left, right = left.strip(), right.strip()
    if not left or not right:
        return False
    if left == right:
        return True
    # 去掉 glob 通配后缀后比较前缀，覆盖 `src/**` 与 `src/x.py` 这类包含关系。
    left_base = left.rstrip("*").rstrip("/")
    right_base = right.rstrip("*").rstrip("/")
    if not left_base or not right_base:
        return False
    return (
        left_base == right_base
        or left_base.startswith(right_base + "/")
        or right_base.startswith(left_base + "/")
    )


def find_parallel_conflicts(
    cards: list[tuple[Path, dict[str, str]]],
    active_tasks: list[tuple[str, str]],
) -> list[str]:
    """暴露同一活跃区里写入白名单重叠的任务卡。

    多个任务同时施工时若白名单交叉，两个执行体会互相覆盖同一文件，
    表现为“任务串了、改动对不上”。这里在开工阶段直接拦出来。
    """
    active_cards = [
        (path, card)
        for path, card in cards
        if card.get("mode") in {"execute", "plan"} and card_is_linked(card, active_tasks)
    ]
    reports: list[str] = []
    for index, (left_path, left) in enumerate(active_cards):
        left_id = left.get("ticket_id") or left_path.stem
        left_paths = split_paths(left.get("write_whitelist", ""))
        for right_path, right in active_cards[index + 1:]:
            right_id = right.get("ticket_id") or right_path.stem
            right_paths = split_paths(right.get("write_whitelist", ""))
            shared = sorted(
                {
                    f"{a} ↔ {b}"
                    for a in left_paths
                    for b in right_paths
                    if paths_overlap(a, b)
                }
            )
            if shared:
                reports.append(
                    f"{left_id} 与 {right_id} 写入白名单重叠：{'、'.join(shared)}；"
                    f"并行施工会互相覆盖，需拆成串行或重新划分边界。"
                )
    return reports


def find_dependency_blockers(
    cards: list[tuple[Path, dict[str, str]]],
    active_tasks: list[tuple[str, str]],
    flow: Path,
) -> list[str]:
    """检查活跃任务的前置依赖是否仍未交付。

    多端并行常见形态是 B 端依赖 A 端的接口契约；若 B 先开工会做出无法
    对接的实现。依赖以任务卡 `depends_on` 声明，未完成时直接拦在开工阶段。
    """
    done: set[str] = set()
    history = flow / "history" / "tasks"
    if history.is_dir():
        for path in history.glob("*.md"):
            done.add(path.stem)
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.lower().startswith("ticket_id:"):
                    done.add(line.split(":", 1)[1].strip())

    reports: list[str] = []
    for path, card in cards:
        if card.get("mode") not in {"execute", "plan"}:
            continue
        if not card_is_linked(card, active_tasks):
            continue
        raw = card.get("depends_on", "").strip()
        if not raw or raw in {">", "|", "-", "无"}:
            continue
        ticket = card.get("ticket_id") or path.stem
        pending = [
            dep
            for dep in split_paths(raw)
            if dep and dep not in done and not (flow / "history" / "tasks" / f"{dep}.md").exists()
        ]
        if pending:
            reports.append(
                f"{ticket} 前置依赖未交付：{'、'.join(pending)}；"
                f"完成并归档前置任务前不得开工。"
            )
    return reports


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
        hints.append(
            "原生交接：Plan 路由必须调用 Codex 原生 Plan 模式做只读拆解；"
            "任务目标用原生 goal / create_goal 登记，规划完成后转 Execute Mode。"
        )
    if execute_cards:
        hints.append(
            "Execute 路由：" + "、".join(card.get("ticket_id", path.name) for path, card in execute_cards)
            + "；实现阶段：先写失败测试再最小实现 (TDD)，留下 Exit 0 证据。"
        )
        hints.append(
            "原生交接：Execute 只做实现与 TDD，不重复规划；"
            "SDD/TDD/ATDD/BDD 是执行要求，不是任务卡上的标签，必须有真实测试与证据。"
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
        hints.append(
            "原生交接：handoff 完成后用原生 goal 的 update_goal 标记目标完成，"
            "再开新会话时由 flow-boot 重新认领。"
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
    parallel_conflicts: list[str],
    dependency_blockers: list[str],
    claim_reports: list[str],
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
    if parallel_conflicts:
        status.append(
            f"- 并行冲突 {len(parallel_conflicts)} 组：活跃任务写入白名单交叉，"
            f"并行施工会互相覆盖，需拆成串行或重新划分边界。"
        )
        status.extend(f"  - {report}" for report in parallel_conflicts[:3])
        if len(parallel_conflicts) > 3:
            status.append(f"  - …另有 {len(parallel_conflicts) - 3} 组，详见 flow/tasks/ 白名单。")
    if claim_reports:
        status.extend(f"- {report}" for report in claim_reports)
    if dependency_blockers:
        status.extend(f"- {report}" for report in dependency_blockers)
    if not blockers and not parallel_conflicts and not dependency_blockers and not claim_reports:
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
    parallel_conflicts = find_parallel_conflicts(cards, active_tasks)
    dependency_blockers = find_dependency_blockers(cards, active_tasks, project_root / "flow")
    claim_reports = claim_active_tasks(
        project_root / "flow", cards, active_tasks, args.thread_id
    )
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
                parallel_conflicts,
                dependency_blockers,
                claim_reports,
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
