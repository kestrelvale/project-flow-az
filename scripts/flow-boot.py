#!/usr/bin/env python3
"""project-flow 开工入口：定位项目、按需热同步、执行只读审计。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
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
DISTILL_SCRIPT = SKILL_DIR / "scripts" / "flow-distill.py"
DELIVER_SCRIPT = SKILL_DIR / "scripts" / "flow-deliver.py"

_GATE_SPEC = importlib.util.spec_from_file_location("flow_gate", GATE_SCRIPT)
assert _GATE_SPEC and _GATE_SPEC.loader
FLOW_GATE = importlib.util.module_from_spec(_GATE_SPEC)
_GATE_SPEC.loader.exec_module(FLOW_GATE)

_DELIVER_SPEC = importlib.util.spec_from_file_location("flow_deliver", DELIVER_SCRIPT)
assert _DELIVER_SPEC and _DELIVER_SPEC.loader
FLOW_DELIVER = importlib.util.module_from_spec(_DELIVER_SPEC)
_DELIVER_SPEC.loader.exec_module(FLOW_DELIVER)

PLAN_TASK_RE = re.compile(r"^\s*[-*]\s*\[([ \-✕xX])\]\s+(.+?)\s*$")
CARD_KEYS = (
    "ticket_id",
    "goal",
    "objective",
    "mode",
    "method",
    "scope",
    "write_whitelist",
    "verify_command",
    "acceptance",
    "red_test",
    "schema",
    "depends_on",
    "next_agent",
    "next_action",
)
FOCUS_HEADING_MARKERS = ("当前聚焦", "当前任务", "施工队列")
CLAIMS_DIR = "claims"
CLAIM_TTL_HOURS = 12

# 交付回执目录：由 flow-deliver.py 写入，是“这一轮真的收过工”的唯一机器凭证。
DELIVERIES_DIR = "deliveries"
BUDGET_DIR = "budget"
# 同时兼容 P0-3、P-FRONT-3、P0-26 这类编号，别只认字母开头的旧写法。
TICKET_IN_TITLE_RE = re.compile(r"([A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-\d+)")


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
    intent: str = "",
    dependency_blockers: list[str] | None = None,
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
    # 依赖未交付的任务不许被认领，否则会话会抱着做不了的卡占地。
    blocked = set()
    for report in dependency_blockers or []:
        blocked.add(report.split(" ", 1)[0])
    for path, card in cards:
        if card.get("mode") not in {"execute", "plan"}:
            continue
        if not card_is_linked(card, active_tasks):
            continue
        ticket = card.get("ticket_id") or path.stem
        if ticket in blocked:
            continue
        # 多端并行时每个会话只认领与自己意图匹配的卡，避免一张会话吞掉整条队列。
        if intent and not intent_matches(intent, active_tasks, [(path, card)]):
            continue
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


def read_delivered_tickets(flow: Path) -> set[str]:
    """收集 flow/deliveries/ 里的交付回执编号。"""
    delivered: set[str] = set()
    receipt_dir = flow / DELIVERIES_DIR
    if not receipt_dir.is_dir():
        return delivered
    for path in receipt_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ticket = str(data.get("ticket_id", "")).strip()
        if ticket:
            delivered.add(ticket)
    return delivered


def audit_deliveries(flow: Path, pending_tasks: list[str]) -> list[str]:
    """待验收任务必须能查到交付回执，否则这一轮根本没走收工流程。

    依据：2026-09-22 的 o2o 会话跑了 7 次 flow-deliver.py，用户可见回复里
    0 次出现看板；只靠 AGENTS.md 的口头约定管不住。回执让“没交付”变成
    下次开工必须点名的债务，而不是静默消失。
    """
    delivered = read_delivered_tickets(flow)
    missing: list[str] = []
    unknown: list[str] = []
    for title in pending_tasks:
        match = TICKET_IN_TITLE_RE.search(title)
        if not match:
            unknown.append(title.split(":")[0].strip()[:40])
            continue
        if match.group(1) not in delivered:
            missing.append(match.group(1))
    missing = list(dict.fromkeys(missing))
    if not pending_tasks:
        return []
    reports = [
        f"待验收 {len(pending_tasks)} 项：有回执 {len(pending_tasks) - len(missing) - len(unknown)}"
        f" / 查无回执 {len(missing)} / 编号无法识别 {len(unknown)}"
    ]
    if missing:
        reports.extend(f"  - {ticket}：未运行 flow-deliver.py 或回执未落盘" for ticket in missing[:5])
        if len(missing) > 5:
            reports.append(f"  - …另有 {len(missing) - 5} 项，详见 flow/{DELIVERIES_DIR}/")
    if unknown:
        shown = "、".join(unknown[:3])
        reports.append(f"  - 无编号条目（无法核对回执）：{shown}")
    return reports


def handoff_is_acceptable(flow: Path, thread_id: str = "") -> bool:
    """核销熔断的交接棒质量门槛：字段齐备 + SDD 蒸馏 + 不是照抄用户消息。

    只比对「顶部标题是否变了」能被一句话绕过——实测写一条
    `## 2026-09-23 · T1 · 交了` + `- 干了点活` 就能解除柔性阻塞继续施工，
    机制等于形同虚设。所以核销必须走校验，而不是只看标题。

    thread_id 必须传真实值：照抄检测要拿本线程的用户消息当比对源，
    传假 id 会让比对源为空、照抄检测恒真，等于把这道门悄悄关掉。
    """
    if not DISTILL_SCRIPT.is_file():
        return True
    args = [
        sys.executable,
        str(DISTILL_SCRIPT),
        "handoff",
        "--project",
        str(flow.parent),
    ]
    if thread_id:
        args.extend(["--thread-id", thread_id])
    result = subprocess.run(
        args,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def latest_receipt_path(flow: Path, thread_id: str = "") -> Path | None:
    """取「开工前那条」熔断回执，作为核销参照。

    两条硬约束（都来自实测事故）：
    1) 不能取本次开工刚写的那条——它的 `handoff_head` 捕获的是此刻的顶部标题，
       拿它比「标题有没有变」必然相等，柔性阻塞会永远核销不掉；
    2) **必须优先取属于本会话的回执**。多会话并发写同一个项目时，
       机械取「倒数第二条」会取到别人的回执；而核销要求来源会话匹配，
       于是本会话自己写的合法交接棒永远核销不掉 —— 表现为反复 STOP / 反复柔性阻塞
       （2026-09-23 thread 01a0c24b 实测：回执 head=PMO、顶部已是它自己的 Wave0 交接棒，
       参照却取到了 thread 01a0c297 的回执）。

    取法：在「排除最新那条」之后，优先选 thread_id 匹配的回执（若有），否则取最近的。
    """
    receipt_dir = flow / BUDGET_DIR
    if not receipt_dir.is_dir():
        return None
    receipts = sorted(receipt_dir.glob("*-stop.json"))
    if not receipts:
        return None
    if len(receipts) == 1:
        return receipts[0]
    candidates = receipts[:-1]  # 排除本次开工刚写的那条
    if thread_id:
        for path in reversed(candidates):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(data.get("thread_id") or "") == thread_id:
                return path
    return candidates[-1]


def read_pending_stop(flow: Path, thread_id: str = "", receipt_path: Path | None = None) -> tuple[Path | None, dict[str, object]]:
    """最近一次预算 STOP 是否还没被交接棒消化。

    实测 2026-09-21 的 8 个 zhengjie 分端会话：flow-budget.py 每次都判出 STOP
    （最高累积 371 次工具调用），但只有 1 个会话把接力提示词写进过回复，
    其余一路施工到单次输入 555k~682k，被 Codex 自动压缩——压缩摘要会把
    「所有用户消息」回灌成一条消息，正是用户看到的汇报冗余与漂移源。
    触发层一直是正常的，缺的是把 STOP 落盘并在下一轮强制核销。
    """
    receipt_dir = flow / BUDGET_DIR
    if not receipt_dir.is_dir():
        return None, {}
    if receipt_path is not None:
        latest = receipt_path
    else:
        receipts = sorted(receipt_dir.glob("*-stop.json"))
        if not receipts:
            return None, {}
        latest = receipts[-1]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, {}
    # 交接棒是否补上：标题与熔断当时不同 **且** 通过蒸馏/字段校验 **且** 来源会话对得上。
    # 只看标题会被一句占位标题绕过（见 handoff_is_acceptable 注释）；
    # 只看新标题又会让并发会话的交接棒替别人核销熔断（2026-09-23 实测踩到）。
    title, _ = latest_handoff(flow)
    owner = str(data.get("thread_id") or "").lower()
    declared = handoff_thread_id(flow)
    if (
        title
        and title != str(data.get("handoff_head", ""))
        and handoff_is_acceptable(flow, thread_id)
        and (not owner or declared == owner)
    ):
        return None, data
    return latest, data


def render_stop_reports(
    flow: Path, thread_id: str = "", receipt_path: Path | None = None
) -> list[str]:
    receipt, data = read_pending_stop(flow, thread_id, receipt_path)
    if receipt is None:
        return []
    reasons = "；".join(str(reason) for reason in data.get("reasons", [])[:3])
    reports = [
        f"上一轮预算 STOP 未交接：输入 {data.get('input_tokens', 0)} tokens / "
        f"轮次 {data.get('rounds', 0)} / 工具调用 {data.get('tool_calls', 0)}"
        + (f"（{reasons}）" if reasons else "")
    ]
    reports.append(f"  - 回执：{receipt.relative_to(flow.parent)}")
    reports.append(
        "  - 必须补写 flow/进展.md 顶部 SDD 蒸馏交接棒（规格点 SPE-n / 待办 / 证据 / 下一步）"
        "与 flow/specs/<ticket>.md 规格点台账，并把熔断回执里的接力提示词交给新会话；"
        "否则本会话继续施工只会把上下文推到自动压缩区。"
    )
    # 用户反馈「要求交接却没有交接提示词」：回执里存着当时生成的提示词，
    # 开工时直接贴出来，避免还要再跑一次命令去捞。
    stored = str(data.get("handoff_prompt") or "").strip()
    if stored:
        reports.append("  - 接力提示词（可直接复制给新会话）：")
        reports.extend(f"    {line}" for line in stored.splitlines())
    # 为什么还没核销：把「谁该核销、当前声明的是谁」摊开，避免干等。
    owner = str(data.get("thread_id") or "")
    declared = handoff_thread_id(flow)
    if owner and declared != owner:
        reports.append(
            f"  - 未核销原因：本次熔断属于会话 `{owner[:12]}`，"
            f"而当前交接棒声明的是 `{(declared or '未声明')[:12]}`。"
            f"只有当事会话写的交接棒（带 `thread={owner}`）才能核销这条熔断。"
        )
    return reports


def run_distill_checks(project_root: Path, thread_id: str) -> tuple[list[str], list[str]]:
    """跑 flow-distill 的两道校验，返回（问题, 规格点回收提示）。

    问题会被并进路由阻塞；提示给新会话当唯一待办源——已完成规格点不得重跑，
    这正是「中断后反复执行同一个需求点」的解药。
    """
    if not DISTILL_SCRIPT.is_file():
        return [], []
    spec = subprocess.run(
        [sys.executable, str(DISTILL_SCRIPT), "spec", "--project", str(project_root)],
        text=True,
        capture_output=True,
    )
    spec_lines = [line for line in (spec.stdout or "").splitlines() if line.strip()]
    problems = [
        line.strip()[2:].strip()
        for line in spec_lines
        if line.strip().startswith("! ")
    ]
    notes: list[str] = []
    if spec_lines and "无规格点台账" not in spec.stdout:
        notes.append("### project-flow 规格点回收（续跑唯一待办源）")
        notes.extend(line for line in spec_lines[1:26])
    if thread_id:
        handoff = subprocess.run(
            [
                sys.executable,
                str(DISTILL_SCRIPT),
                "handoff",
                "--project",
                str(project_root),
                "--thread-id",
                thread_id,
            ],
            text=True,
            capture_output=True,
        )
        if handoff.returncode != 0:
            problems.extend(
                line.strip()[2:].strip()
                for line in (handoff.stdout or "").splitlines()
                if line.strip().startswith("! ")
            )
    return problems, notes


# plan.md 里这些章节属于“已终结”，其内容应物理归档，不得长期驻留活跃控制面。
ARCHIVED_HEADING_RE = re.compile(r"归档|Archived|已完成|已废弃|废弃任务")

# 任务体量上限：超过即视为“巨型卡”，必须在 plan 阶段拆成原子卡再施工。
# 依据：一次会话的预算是 100 次工具调用，超体量的卡必然中途 STOP、任务烂尾。
MAX_WHITELIST_PATHS = 8
MAX_ACCEPTANCE_SCENARIOS = 4
MAX_ACCEPTANCE_STEPS = 5
MAX_SCOPE_LINES = 12
MAX_SCOPE_ITEMS = 8

# 交接棒结构化四字段：缺一项，下一个会话就得重读 plan + 任务卡 + 进展才能拼状态，
# 这部分重复劳动实测会吃掉大量预算。字段名保持简短以降低书写成本。
HANDOFF_FIELDS = ("现状", "还剩", "卡在哪", "下一步")
# 上限按实测重标（2026-09-23 取样 zhengjie-hrm 229 条真实交接棒）：
#   p25 1151 / p50 1543 / p75 1979 / p90 2646 / max 5965，**72% 超过旧的 1200**。
# 1200 是「只写现状/还剩/卡在哪/下一步」时代的遗留值；v4.15.0 之后交接棒还要带
# SDD 蒸馏结构（规格点 SPE-n / 待办 / 证据 / 下一步），旧值必然误伤合格交接棒
# （实测有一条 1532 字节的合格交接棒被拦下）。防「复述背景」已由更精准的照抄检测承担
# （flow-distill：最长连续照抄 >= 400 字符或比例 >= 60%），所以这里只做体积兜底，
# 取 4000（> p97），仍能挡住 6KB 级别的整段复述。
MAX_HANDOFF_BYTES = 4000
# 交接棒必须声明来源 Codex 线程 id（`thread=<uuid>`），且只有当事会话能核销自己的熔断。
# 依据：2026-09-23 实测「我的交接棒被并发会话顶掉，导致上一轮 STOP 未交接」——
# 并发会话各写各的交接棒，谁都能把别人的熔断当已交接。
HANDOFF_THREAD_RE = re.compile(
    r"thread=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def handoff_thread_id(flow: Path) -> str:
    """取交接棒声明的来源 Codex 线程 id（标题优先，正文兜底）。"""
    title, body = latest_handoff(flow)
    match = HANDOFF_THREAD_RE.search(title) or HANDOFF_THREAD_RE.search(body)
    return match.group(1).lower() if match else ""
# 中段复查节奏，与 flow-budget.py 的 --guard 输出保持一致。
GUARD_FILE = "guard.json"
GUARD_STALE_CALLS = 50


def read_guard_staleness(flow: Path, budget_output: str) -> str:
    """中段复查是否过期。返回空串=不过期；否则返回可直接打印的阻塞说明。

    依据：实测 P4 会话在**同一个 turn 内**跑了 200+ 次工具调用，开工那一次预算判定
    早就过期（当时只有 38%），一路堆到单次输入 60.8 万才被模型自己「摆烂」暴露。
    AGENTS.md 明令不装 Hook，所以唯一可强制的时点是「下一个可观测入口」——这里。
    """
    checkpoint = flow / BUDGET_DIR / GUARD_FILE
    current = 0
    for line in budget_output.splitlines():
        match = re.search(r"工具调用 (\d+)", line)
        if match:
            current = int(match.group(1))
            break
    if not current or not checkpoint.is_file():
        return ""
    try:
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    last = int(data.get("tool_calls") or 0)
    if current - last < GUARD_STALE_CALLS:
        return ""
    return (
        f"中段复查已过期：上次检查点在 {last} 次工具调用，现在 {current} 次"
        f"（间隔 {current - last} ≥ {GUARD_STALE_CALLS}）。先跑 "
        "`python3 ~/.codex/skills/project-flow-az/scripts/flow-budget.py --guard --project .`，"
        "超线就立即交接再开新会话。"
    )


def latest_handoff(flow: Path) -> tuple[str, str]:
    """取 flow/进展.md 顶部第一条记录（标题 + 正文）。"""
    progress = flow / "进展.md"
    if not progress.is_file():
        return "", ""
    lines = progress.read_text(encoding="utf-8", errors="replace").splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("## ") or line.startswith("### "):
            start = index
            break
    if start is None:
        return "", ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## ") or lines[index].startswith("### "):
            end = index
            break
    block = lines[start:end]
    return block[0].strip(), "\n".join(block)


def check_handoff_schema(flow: Path, stopped: bool) -> list[str]:
    """校验顶部交接棒是否写全四字段。

    只在上一轮因预算 STOP 中断时强制：那种情况下新会话完全依赖交接棒
    还原现场，字段缺一就必须重读全部文件，等于把熔断成本再付一遍。
    """
    if not stopped:
        return []
    title, body = latest_handoff(flow)
    if not title:
        return ["进展.md 顶部没有交接记录：熔断后必须留下结构化交接棒。"]
    problems: list[str] = []
    missing = [field for field in HANDOFF_FIELDS if f"{field}" not in body]
    if missing:
        problems.append(
            f"交接棒缺少字段：{'、'.join(missing)}；"
            f"必须补全「现状 / 还剩 / 卡在哪 / 下一步」，否则新会话需重读全部文件。"
        )
    if not HANDOFF_THREAD_RE.search(title) and not HANDOFF_THREAD_RE.search(body):
        problems.append(
            "交接棒未声明来源 Codex 线程 id：标题或正文必须带 `thread=<当前会话 thread id>`。"
            "没有它，就无法区分「当事会话的交接」与「并发会话顺手写的交接」，"
            "熔断不会被核销（实测 2026-09-23 踩到：交接棒被并发会话顶掉）。"
        )
    if len(body.encode("utf-8")) > MAX_HANDOFF_BYTES:
        problems.append(
            f"交接棒 {len(body.encode('utf-8'))} 字节（上限 {MAX_HANDOFF_BYTES}）："
            f"过长说明在复述背景，应只写现状、剩余、阻塞与下一步。"
        )
    return problems


def progress_has_stop(flow: Path) -> bool:
    """上一轮是否以预算 STOP / 熔断收尾。"""
    _, body = latest_handoff(flow)
    return any(marker in body for marker in ("STOP", "熔断", "预算"))


def measure_card_size(card: dict[str, str]) -> list[str]:
    """暴露体量过大、必然中途熔断的任务卡。

    zhengjie 的 P3 卡把 38 个页面 + 43 个原型节点塞进一张卡，会话跑到
    100 次工具调用被迫 STOP，任务永远收不了口。这类卡必须在 plan 阶段拆。
    """
    problems: list[str] = []
    paths = split_paths(card.get("write_whitelist", ""))
    acceptance = card.get("acceptance", "")
    scenarios = len(re.findall(r"Given", acceptance))
    # 验收里用 `→` 串起的长链，意味着单卡要贯通多个独立环节，
    # 这类卡实测必然在一个会话内熔断。
    steps = acceptance.count("→")
    scope = card.get("scope", "")
    scope_lines = len([line for line in scope.splitlines() if line.strip()])
    # scope 里的编号条目就是卡内并列交付物；条目越多，越不可能一次收口。
    scope_items = len(re.findall(r"(?m)^\s*\d+[.、]", scope))
    if len(paths) > MAX_WHITELIST_PATHS:
        problems.append(
            f"写入白名单 {len(paths)} 条（上限 {MAX_WHITELIST_PATHS}）："
            f"改动面过大，应拆成多张原子卡"
        )
    if scenarios > MAX_ACCEPTANCE_SCENARIOS:
        problems.append(
            f"验收场景 {scenarios} 个（上限 {MAX_ACCEPTANCE_SCENARIOS}）："
            f"单卡验收面过大，应按场景拆卡"
        )
    if steps > MAX_ACCEPTANCE_STEPS:
        problems.append(
            f"验收链路 {steps} 段（上限 {MAX_ACCEPTANCE_STEPS}）："
            f"单卡要贯通过多环节，应按环节拆卡"
        )
    if scope_items > MAX_SCOPE_ITEMS:
        problems.append(
            f"范围并列交付物 {scope_items} 项（上限 {MAX_SCOPE_ITEMS}）："
            f"一张卡塞了多个独立目标，应按交付物拆卡"
        )
    elif scope_lines > MAX_SCOPE_LINES:
        problems.append(
            f"范围描述 {scope_lines} 行（上限 {MAX_SCOPE_LINES}）："
            f"边界过于宽泛，应缩窄后拆卡"
        )
    return problems


def find_oversized_cards(
    cards: list[tuple[Path, dict[str, str]]],
    active_tasks: list[tuple[str, str]],
) -> list[str]:
    """体量超限即报，不限于活跃区。

    未被当前 plan.md 绑定的卡同样会被后续会话捡起来施工，若只查活跃区，
    巨卡会躲在 flow/tasks/ 里等到开工才暴雷。
    """
    reports: list[str] = []
    for path, card in cards:
        problems = measure_card_size(card)
        if problems:
            ticket = card.get("ticket_id") or path.stem
            reports.append(f"{ticket}：" + "；".join(problems))
    return reports


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
    blocked: bool = False,
) -> list[str]:
    if blocked:
        # 柔性阻塞：进程不失败、任务不中断，但本轮路由降级为 handoff-only。
        # 依据 2026-09-23 取证：P3/P0/P4/P-FRONT-* 会话里 flow-budget 判出 STOP
        # （最多 16 次）后无人执行，会话一路跑到 556k~682k 被 Codex 自动压缩，
        # 压缩摘要把全部用户消息回放成 12k~29k 字节的「汇报」。
        return [
            "Handoff 路由（柔性阻塞）：上一轮预算 STOP 尚未交接，本轮只允许交接落盘。",
            "允许：写 flow/进展.md 顶部 SDD 蒸馏交接棒（规格点/待办/证据/下一步）"
            "+ flow/specs/<ticket>.md 规格点台账，并跑 flow-deliver.py 交付。",
            "禁止：登记新意图、开新的 Execute 卡、修改业务代码、启停服务。",
            "解除：交接棒与台账落盘后开新会话，flow-boot.py 自动核销熔断回执。",
            "任务偏大时不要硬推：回 flow/plan.md 按 SDD 把本卡拆成原子卡，再交给新会话。",
        ]
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
    oversized_cards: list[str],
    handoff_problems: list[str],
    delivery_reports: list[str],
    stop_reports: list[str],
    soft_blocked: bool = False,
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
    if oversized_cards:
        status.append(
            f"- 巨型任务卡 {len(oversized_cards)} 张：超出单会话预算，"
            f"必须在 Plan 阶段按场景拆成原子卡，否则必然中途熔断。"
        )
        status.extend(f"  - {report}" for report in oversized_cards[:3])
        if len(oversized_cards) > 3:
            status.append(f"  - …另有 {len(oversized_cards) - 3} 张。")
    if handoff_problems:
        status.extend(f"- {report}" for report in handoff_problems)
    if (
        not blockers
        and not parallel_conflicts
        and not dependency_blockers
        and not claim_reports
        and not oversized_cards
        and not handoff_problems
    ):
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

    status.extend(["", "## 📨 交付回执"])
    if delivery_reports:
        status.extend(f"- {report}" for report in delivery_reports)
    else:
        status.append("- 无待验收任务，无需交付回执")

    status.extend(["", "## ⏸ 熔断交接"])
    if soft_blocked:
        # 阻塞来源有两类：未核销的熔断回执，或中段复查过期。
        # 提示不能写在 if stop_reports 里面，否则「只有复查过期」时线号是空的。
        status.append(
            "- 【柔性阻塞】本轮路由已降级为 handoff-only：只允许写交接棒与规格点台账；"
            "禁止登记新意图、禁止业务施工（进程不失败，解除条件是交接落盘）。"
        )
    if stop_reports:
        status.extend(f"- {report}" for report in stop_reports)
    else:
        status.append("- 无未交接的预算熔断")

    status.extend(["", "## ♻️ 回收建议"])
    if stop_reports:
        status.append(
            "- 上一轮预算已 STOP 但交接棒缺失：先补交接棒并开新会话，"
            "否则上下文会继续膨胀到自动压缩区，压缩摘要会把全部历史消息回灌造成漂移。"
        )
    debt = any("查无回执 " in report and "查无回执 0" not in report for report in delivery_reports)
    debt = debt or any("无法识别 " in report and "无法识别 0" not in report for report in delivery_reports)
    if debt:
        status.append(
            "- 存在“已进待验收却查无交付回执”的任务：说明收工看板从未生成，"
            "必须补跑 flow-deliver.py 并把看板贴进回复。"
        )
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


def render_sdd_gate(
    intent: str,
    active_tasks: list[tuple[str, str]],
    cards: list[tuple[Path, dict[str, str]]],
    blocked: bool = False,
) -> list[str]:
    if blocked:
        return [
            "### project-flow SDD 登记门（柔性阻塞）",
            "",
            f"- 本轮意图：{intent or '（未提供）'}",
            "- 状态：上一轮预算 STOP 尚未交接，本轮拒绝登记新意图、拒绝开新任务卡。",
            "- 先做：把上一轮的规格点与待办蒸馏进 `flow/进展.md` 顶部交接棒与 "
            "`flow/specs/<ticket>.md`，再开新会话继续。",
            "- 原因：会话一旦进入压缩区，压缩摘要会把全部历史用户消息回放成汇报，"
            "新会话只能重读历史，等于熔断白做。",
        ]
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

    # thread-id 兜底：AGENTS.md 只要求传 --intent，若不补 CODEX_THREAD_ID，
    # 交接棒核销会因为取不到用户消息比对源而判失败 → 柔性阻塞永远解不开。
    thread_id = args.thread_id or os.environ.get("CODEX_THREAD_ID", "")

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
    oversized_cards = find_oversized_cards(cards, active_tasks)
    flow_dir = project_root / "flow"
    # 预算先跑一次并留下来：既用于中段复查的过期判定，也在末尾原样打印，
    # 避免为了拿工具调用数再解析一遍 rollout。
    budget_result = None
    if not args.skip_budget:
        budget_result = subprocess.run(
            [
                sys.executable,
                str(BUDGET_SCRIPT),
                "--intent",
                args.intent or "继续当前 project-flow 活跃任务",
                *(["--thread-id", thread_id] if thread_id else []),
                "--project",
                str(project_root),
            ],
            text=True,
            capture_output=True,
        )
    budget_output = (budget_result.stdout or "") if budget_result else ""
    # 核销参照必须是「开工前那条」：本次 flow-budget 刚写的回执 handoff_head
    # 捕获的是此刻的顶部标题，拿它当参照必然相等 → 柔性阻塞永远核销不掉。
    # 所以这里在预算跑完之后取，由 latest_receipt_path 排除刚写的这条。
    pending_receipt = latest_receipt_path(flow_dir, thread_id)
    stop_reports = render_stop_reports(flow_dir, thread_id, pending_receipt)
    guard_problem = read_guard_staleness(flow_dir, budget_output)
    soft_blocked = bool(stop_reports) or bool(guard_problem)
    distill_problems, distill_notes = run_distill_checks(project_root, thread_id)
    handoff_problems = check_handoff_schema(
        flow_dir, progress_has_stop(flow_dir) or bool(stop_reports)
    )
    handoff_problems.extend(distill_problems)
    if guard_problem:
        handoff_problems.append(guard_problem)
    if "上轮回复缺失接力提示词" in budget_output:
        # 用户反馈：「应该在对话框上打印出交接提示词再结束，而不是直接熔断」。
        # 这条来自 flow-budget 的机检；放到路由阻塞里，模型开工就被点名。
        handoff_problems.append(
            "上一轮熔断没有把接力提示词贴进回复：本轮必须把 flow-budget 输出的那段"
            "「project-flow 接力提示词」原样复制到回复里，再结束本轮；只写「已熔断」不算交接。"
        )
    delivery_reports = audit_deliveries(project_root / "flow", pending_tasks)
    claim_reports = (
        []
        if soft_blocked
        else claim_active_tasks(
            project_root / "flow",
            cards,
            active_tasks,
            thread_id,
            args.intent,
            dependency_blockers,
        )
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
                oversized_cards,
                handoff_problems,
                delivery_reports,
                stop_reports,
                soft_blocked,
            )
        )
    )
    if distill_notes:
        print("\n" + "\n".join(distill_notes))
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
    for hint in route_hint(active_tasks, cards, unmanaged_tasks, args.intent, soft_blocked):
        print(f"- 路由: {hint}")
    sdd_gate = render_sdd_gate(args.intent, active_tasks, cards, soft_blocked)
    if sdd_gate:
        print("\n" + "\n".join(sdd_gate))
    print("\nproject-flow 会话预算检查点")
    print(
        "- 中段复查：本会话每 50 次工具调用复跑一次 "
        "`python3 ~/.codex/skills/project-flow-az/scripts/flow-budget.py --guard --project .`；"
        "超线立即交接，不要等到下一轮开工才发现。"
    )
    print("- 阈值是「占有效窗口的比例」，随模型自适应；具体数字见下方预算输出。")
    if budget_output:
        sys.stdout.write(budget_output)
    budget_code = budget_result.returncode if budget_result else 0
    return max(audit.returncode, gc.returncode, gate_code, budget_code)


if __name__ == "__main__":
    raise SystemExit(main())
