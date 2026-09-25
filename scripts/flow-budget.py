#!/usr/bin/env python3
"""会话预算门禁：从当前 Codex session 读取真实 token 用量并输出接力提示。"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

# 阈值按**比例**标定，锚在会话自己声明的有效窗口上（不写死绝对值）。
#
# 推导依据（2026-09-23 取证 8 个分端会话 rollout，实测窗口 950000）：
#   1. 窗口的来源：Codex 用「模型 context_window × effective_context_window_percent」。
#      会话里 model_context_window 就是有效窗口——中继会话一律 950000（=0.95×1e6），
#      原生 GPT 是 258400（=0.95×272k）。所以硬编码绝对值对某个模型必然错。
#   2. 压缩触发点实测 ≈ 104.9% 窗口（一次请求输入 996370 时压缩才安装成功）。
#   3. 真正先失效的不是压缩，而是模型：deepseek-v4.1-flash 在单次输入 556166 /
#      574491 / 608167 时连续三次**放弃干活、把历史用户消息原样回放成汇报**，
#      = 58.5% 窗口。这才是用户看到「汇报带上所有用户消息」的真身。
#   4. 单轮上下文增量实测 p50 30982 / p90 125246 / max 289972，p90 = 13.2% 窗口。
#
# 用户 2026-09-23 拍板：WARN 45% / STOP 50%（要用满窗口）。
# 代价已量化并记入 CHANGELOG：50% 时距实测失效起点(58.5%)只剩 8.5% 窗口
# = 950k 下 8.1 万 tokens，而单轮增量 p90 是 12.5 万 → 约 0.65 个 p90 轮；
# 45% 时是 1.03 个轮。也就是说 50% 线下，一个中等偏重的轮次就可能从 STOP
# 直接越过失效点，交接还没落地就中招——这是知情的取舍，不是疏漏。
WARN_RATIO = 0.45
STOP_RATIO = 0.50
# 实测的模型失效起点（deepseek-v4.1-flash 在 58.5% 窗口处开始回放用户消息）。
# 只用于提示文案与标定锁，不参与判级：STOP_RATIO 必须小于它，否则熔断晚于模型失效。
MODEL_FAILURE_RATIO = 0.585
# 窗口读不到时（session 缺 model_context_window）才用绝对值兜底：
# 按实测中继窗口 950k × 45% / 50% ≈ 42.8 万 / 47.5 万。
WARN_INPUT_TOKENS = 420_000
STOP_INPUT_TOKENS = 470_000
# 轮次与工具调用是漂移兜底：只在高轮次/高调用量但 token 还没顶到线时接棒，
# 阈值放在 token 线之后，避免再次出现「38% 就报 STOP」的告警疲劳。
WARN_ROUNDS = 15
STOP_ROUNDS = 25
WARN_TOOL_CALLS = 90
STOP_TOOL_CALLS = 160

# 熔断回执目录：STOP 必须落盘，否则交接棒全靠模型自觉。
# 实测 2026-09-21 的 8 个 zhengjie 分端会话：flow-budget 每次都判出 STOP
# （最高累积 371 次工具调用），但 8 个会话里只有 1 个把接力提示词写进过回复，
# 其余直接继续施工到会话结束——触发层正常，强制层缺失。
BUDGET_DIR = "budget"
DELIVERIES_DIR = "deliveries"
# 检查点文件（覆盖式，不是时间戳堆积）：记录「上一次中段复查时的工具调用数」，
# 供开工时判断复查节奏是否已经过期。与熔断回执分开——回执只由开工判定写。
GUARD_FILE = "guard.json"
# 未显式传 --intent 时接力提示词里写的默认任务描述。
DEFAULT_INTENT = "继续当前 project-flow 活跃任务"


def top_handoff_head(flow: Path) -> str:
    """取 进展.md 顶部第一条交接记录的标题行。"""
    progress = flow / "进展.md"
    if not progress.is_file():
        return ""
    for line in progress.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## ") or line.startswith("### "):
            return line.strip()
    return ""


def latest_stop_receipt(project: Path) -> tuple[Path | None, dict]:
    """取最近一条熔断回执（含当时生成的接力提示词）。

    v4.15.4 之前，回执里的 `handoff_prompt` 没有任何入口能读回来：中段复查
    （--guard）只印一句「动作」，柔性阻塞也只说「必须补写交接棒」，于是用户
    看到的现象是「要求交接，却没有交接提示词」。回执里明明存了 973 字符。
    """
    receipt_dir = project / "flow" / BUDGET_DIR
    if not receipt_dir.is_dir():
        return None, {}
    receipts = sorted(receipt_dir.glob("*-stop.json"))
    if not receipts:
        return None, {}
    latest = receipts[-1]
    try:
        return latest, json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, {}


def persist_stop(project: Path, thread_id: str, report: dict, prompt: str) -> Path | None:
    """把此次 STOP 写成回执，供下一轮开工判定“熔断到底交接了没有”。

    回执记录当时的顶部交接标题：新会话只要写了一条新交接棒，标题就会变，
    回执即视为已处理。只靠 进展.md 的 mtime 不行——开工前的日志滚动
    会重写该文件，把“没交接”误判成“已交接”。
    """
    flow = project / "flow"
    if not flow.is_dir():
        return None
    receipt_dir = flow / BUDGET_DIR
    receipt_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now()
    receipt = receipt_dir / f"{stamp:%Y%m%d-%H%M%S}-stop.json"
    receipt.write_text(
        json.dumps(
            {
                "operation": "budget_stop",
                "thread_id": thread_id,
                "stopped_at": stamp.isoformat(timespec="seconds"),
                "level": report.get("level"),
                "reasons": report.get("reasons", []),
                "input_tokens": report.get("input_tokens", 0),
                "context_ratio": report.get("context_ratio", 0.0),
                "rounds": report.get("rounds", 0),
                "tool_calls": report.get("tool_calls", 0),
                "handoff_head": top_handoff_head(flow),
                "handoff_prompt": prompt,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt


def find_session_file(thread_id: str, sessions_root: Path | None = None) -> Path | None:
    root = sessions_root or (Path.home() / ".codex" / "sessions")
    matches = sorted(root.rglob(f"*{thread_id}*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def find_session_files(thread_id: str, sessions_root: Path | None = None) -> list[Path]:
    """取该 thread 的**全部** rollout 文件（新→旧）。

    缺陷（2026-09-23 实测，thread 01a0c297）：同一 thread 会分叉成多个 rollout 文件
    （续跑/重开各写一个）。旧实现只取 mtime 最新的那一个，于是早期文件里
    单次输入 **917,686**（91.7 万，远超熔断线）的峰值完全看不见，
    预算一直报 OK、交接永远不触发——用户看到的就是「到线了却从没触发交接」。
    """
    root = sessions_root or (Path.home() / ".codex" / "sessions")
    return sorted(
        root.rglob(f"*{thread_id}*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )


def classify_level(
    input_tokens: int, context_window: int, rounds_count: int, tool_calls: int
) -> tuple[str, list[str]]:
    """唯一的判级实现（summarize / summarize_thread 共用，避免两处逻辑分叉）。

    口径（2026-09-23 定）：
    - **当前上下文**（单次输入/窗口比例）决定「压缩风险」；
    - **累计规模**（轮次/工具调用，跨 rollout 文件累加）决定「漂移风险」——
      它不随压缩回落，因此能抓住「会话早就该交接了」；
    - 历史峰值只作为证据打印，不单独判级，否则一个已经压缩回落的 thread
      会被永久判 STOP，形成「每次开工都要交接」的死循环。
    """
    ratio = input_tokens / context_window if context_window else 0.0
    reasons: list[str] = []
    if context_window:
        context_stop = ratio >= STOP_RATIO
        context_warn = ratio >= WARN_RATIO
    else:
        context_stop = input_tokens >= STOP_INPUT_TOKENS
        context_warn = input_tokens >= WARN_INPUT_TOKENS
    volume_stop = rounds_count >= STOP_ROUNDS or tool_calls >= STOP_TOOL_CALLS
    volume_warn = rounds_count >= WARN_ROUNDS or tool_calls >= WARN_TOOL_CALLS
    level = "STOP" if (context_stop or volume_stop) else ("WARN" if (context_warn or volume_warn) else "OK")
    if context_window and input_tokens > context_window:
        reasons.append(f"单次输入 {input_tokens} 已超过记录的上下文窗口 {context_window}")
    if context_stop:
        reasons.append(
            f"上下文占用 {ratio:.1%} / 单次输入 {input_tokens}（熔断线 {STOP_RATIO:.0%}"
            + (f" = {int(context_window * STOP_RATIO):,}" if context_window else f" / {STOP_INPUT_TOKENS:,}")
            + f"；实测模型在 {MODEL_FAILURE_RATIO:.1%} 窗口处开始回放用户消息）"
        )
    elif context_warn:
        reasons.append(
            f"上下文占用 {ratio:.1%} / 单次输入 {input_tokens}"
            + (f"（预警线 {WARN_RATIO:.0%}；先按 SDD 拆卡，再交接）" if context_window else "（接近熔断线，先做 SDD 拆卡）")
        )
    if rounds_count >= STOP_ROUNDS:
        reasons.append(f"轮次 {rounds_count} >= {STOP_ROUNDS}")
    elif rounds_count >= WARN_ROUNDS:
        reasons.append(f"轮次 {rounds_count} >= {WARN_ROUNDS}")
    if tool_calls >= STOP_TOOL_CALLS:
        reasons.append(f"工具调用 {tool_calls} >= {STOP_TOOL_CALLS}")
    elif tool_calls >= WARN_TOOL_CALLS:
        reasons.append(f"工具调用 {tool_calls} >= {WARN_TOOL_CALLS}")
    if not reasons:
        reasons.append("预算正常")
    return level, reasons


def summarize(path: Path) -> dict:
    usage = {}
    last_request_usage = {}
    thread_usage_total = {}
    context_window = 0
    rounds: set[str] = set()
    tool_calls = 0
    seen_tool_call_ids: set[str] = set()
    last_event = None
    # 文件内**单次输入峰值**：末尾值可能已被压缩回落（实测 917k 峰值 / 155k 末尾），
    # 只看末尾会漏判「早就该熔断」。
    max_request_input = 0

    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = item.get("type")
            payload = item.get("payload", {})

            if kind == "event_msg":
                event_type = payload.get("type")
                if event_type == "task_started":
                    rounds.add(str(payload.get("turn_id", "")))
                    context_window = payload.get("model_context_window") or context_window
                elif event_type == "token_count":
                    info = payload.get("info", {})
                    last = info.get("last_token_usage") or {}
                    total = info.get("total_token_usage") or {}
                    if last:
                        max_request_input = max(
                            max_request_input, int(last.get("input_tokens") or 0)
                        )
                        last_request_usage = {
                            "input_tokens": int(last.get("input_tokens") or 0),
                            "cached_input_tokens": int(last.get("cached_input_tokens") or 0),
                            "output_tokens": int(last.get("output_tokens") or 0),
                            "total_tokens": int(last.get("total_tokens") or 0),
                        }
                    if total:
                        thread_usage_total = {
                            "input_tokens": int(total.get("input_tokens") or 0),
                            "cached_input_tokens": int(total.get("cached_input_tokens") or 0),
                        }
                        context_window = int(info.get("model_context_window") or context_window)
            elif kind == "response_item":
                if payload.get("type") in {"function_call", "custom_tool_call"}:
                    call_id = str(payload.get("call_id") or payload.get("id") or "")
                    if call_id and call_id not in seen_tool_call_ids:
                        seen_tool_call_ids.add(call_id)
                        tool_calls += 1
            elif kind == "token_usage_record":
                request_usage = payload.get("usage") or {}
                turn_usage = payload.get("turn_token_usage") or request_usage
                thread_usage = payload.get("thread_token_usage") or {}
                if turn_usage:
                    usage = {
                        "input_tokens": int(
                            request_usage.get("input_tokens") or turn_usage.get("input_tokens") or 0
                        ),
                        "cached_input_tokens": int(
                            request_usage.get("cached_input_tokens")
                            or turn_usage.get("cached_input_tokens")
                            or 0
                        ),
                        "output_tokens": int(turn_usage.get("output_tokens") or 0),
                        "total_tokens": int(turn_usage.get("total_tokens") or 0),
                    }
                    if thread_usage:
                        thread_usage_total = {
                            "input_tokens": int(thread_usage.get("input_tokens") or 0),
                            "cached_input_tokens": int(thread_usage.get("cached_input_tokens") or 0),
                        }
                    rounds.add(str(payload.get("root_turn_id") or payload.get("turn_id") or ""))
            last_event = kind

    usage = last_request_usage or usage
    input_tokens = usage.get("input_tokens", 0)
    max_request_input = max(max_request_input, int(input_tokens or 0))
    cached = usage.get("cached_input_tokens", 0)
    ratio = input_tokens / context_window if context_window else 0.0
    cache_ratio = cached / input_tokens if input_tokens else 0.0
    level, reasons = classify_level(input_tokens, context_window, len(rounds), tool_calls)

    return {
        "session_file": str(path),
        "level": level,
        "reasons": reasons,
        "input_tokens": input_tokens,
        "max_input_tokens": max_request_input,
        "cached_input_tokens": cached,
        "cache_ratio": cache_ratio,
        "output_tokens": usage.get("output_tokens", 0),
        "thread_input_tokens": thread_usage_total.get("input_tokens", 0),
        "thread_cached_input_tokens": thread_usage_total.get("cached_input_tokens", 0),
        "context_window": context_window,
        "context_ratio": ratio,
        "rounds": len(rounds),
        "tool_calls": tool_calls,
        # 供跨文件聚合精确去重：不同 rollout 文件的时间区间可能重叠，
        # 单纯累加会重复计数（第 6 点缺口）。
        "turn_ids": sorted(rid for rid in rounds if rid),
        "call_ids": sorted(seen_tool_call_ids),
        "last_event": last_event,
    }


# 交接棒必须是 SDD 蒸馏产物：把用户原话提炼成「要执行的规格点」与「待办清单」。
# 实测 2026-09-21 的 P0/P4 会话：压缩时模型把用户消息原样回放成 12k~29k 字节的
# 复述块当成汇报，既没有规格点也没有销账，新会话只能重读全部历史——熔断白做。
SPEC_LEDGER_TEMPLATE = """### ♻️ 规格点回收台账（每条都要回收，禁止原样照抄用户消息）
- [ ] SPE-1 | <要执行的规格点：可观察的结果> | 证据：
- [ ] SPE-2 | <同上> | 证据：
- [!] SPE-3 | <阻塞规格点> | 证据：<阻塞证据> / 解除条件：<…>"""

HANDOFF_TEMPLATE = """## <日期> · <ticket> · 交接棒（SDD 蒸馏） · thread=<CODEX_THREAD_ID>
- 来源会话：thread=<CODEX_THREAD_ID>（必填。熔断只由「当事会话写的交接棒」核销，
  并发会话顺手写的交接棒不算，避免互相覆盖；见 v4.15.7）
- 规格点(SPE)：SPE-1..n —— 只写「要执行的规格」，不抄用户原话
- 待办(TODO)：`- [ ]` 未做 / `- [-]` 进行中 / `- [x]` 完成 / `- [!]` 阻塞；完成项必须带证据
- 现状：<一句话>
- 还剩：<未回收的 SPE 编号，以及为什么没做完>
- 卡在哪：<阻塞 + 解除条件>
- 下一步：<新会话第一件事，含门禁命令>
- 台账：flow/specs/<ticket>.md（未回收项是唯一待办源，已完成项不得重跑）"""


def summarize_thread(paths: list[Path]) -> dict:
    """把同一 thread 的多个 rollout 文件聚合成一条判定。

    缺陷（2026-09-23 实测 thread 01a0c297）：同一 thread 会分叉成多个 rollout 文件，
    旧实现只看 mtime 最新那一个 —— 早期文件里单次输入峰值 **917,686**（远超 45 万熔断线）
    完全看不见，于是「到线了却从没触发交接」。

    聚合口径：
    - 当前上下文（最新文件的单次输入）→ 走 classify_level 的压缩风险；
    - 轮次 / 工具调用按文件**累加** → 漂移风险（不随压缩回落，能抓住「早就该交接」）；
    - 历史峰值只作证据打印，不单独判级（否则压缩回落后的 thread 会被永久判 STOP）。
    """
    reports = [summarize(path) for path in paths]
    if not reports:
        return {}
    newest = reports[0]  # paths 已按 mtime 新→旧
    # 精确去重：按 turn_id / call_id 取并集，避免文件区间重叠时重复计数（第 6 点缺口）。
    turn_ids: set[str] = set()
    call_ids: set[str] = set()
    for item in reports:
        turn_ids.update(item.get("turn_ids") or [])
        call_ids.update(item.get("call_ids") or [])
    rounds_total = len(turn_ids) if turn_ids else sum(int(item.get("rounds") or 0) for item in reports)
    calls_total = len(call_ids) if call_ids else sum(int(item.get("tool_calls") or 0) for item in reports)
    peak_input = max(
        [int(item.get("max_input_tokens") or 0) for item in reports]
        + [int(item.get("input_tokens") or 0) for item in reports]
    )
    level, reasons = classify_level(
        int(newest.get("input_tokens") or 0),
        int(newest.get("context_window") or 0),
        rounds_total,
        calls_total,
    )
    aggregate = dict(newest)
    aggregate["level"] = level
    aggregate["reasons"] = reasons
    aggregate["rounds"] = rounds_total
    aggregate["tool_calls"] = calls_total
    aggregate["max_input_tokens"] = peak_input
    aggregate["thread_input_tokens"] = sum(
        int(item.get("thread_input_tokens") or 0) for item in reports
    )
    aggregate["session_files"] = [str(path) for path in paths]
    if len(paths) > 1:
        aggregate["reasons"].append(
            f"该 thread 共 {len(paths)} 个 rollout 文件：轮次/工具调用按文件累加；"
            f"历史峰值单次输入 {peak_input:,}（仅作证据，不单独判级）"
        )
    return aggregate


def last_visible_reply(paths: list[Path]) -> str:
    """取该 thread 最后一轮**用户可见的回复**。

    `task_complete.last_agent_message` 就是那一轮的对外回复，是判断
    「熔断提示词有没有真的贴给用户看」的唯一可靠依据。
    """
    for path in paths:  # 新→旧，取最新那个文件的最后一条即可
        last = ""
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if '"last_agent_message"' not in line:
                        continue
                    try:
                        payload = json.loads(line).get("payload") or {}
                    except json.JSONDecodeError:
                        continue
                    if payload.get("type") == "task_complete":
                        last = str(payload.get("last_agent_message") or "") or last
        except OSError:
            continue
        if last:
            return last
    return ""


# 与 flow-boot.py 同款编号识别（P0-3 / P-FRONT-3 / W2-P4-… 都要认）。
TICKET_IN_TITLE_RE = re.compile(r"([A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-\d+)")
PLAN_ITEM_RE = re.compile(r"^[-*]\s*\[([ xX\-!✕])]\s+(.+)$")
# 台账行：`- [state] SPE-n | 规格点 | 证据：…`（与 flow-gate/flow-distill 同款口径）。
SPEC_LINE_RE = re.compile(r"^\s*[-*]\s*\[([ x\-!])]\s*(SPE-\d+)\s*\|\s*(.*?)\s*\|")
# 与 flow-boot.py 同款：只认完整 UUID，避免把截断的 `thread=01a0cd2e-` 当来源。
HANDOFF_THREAD_RE = re.compile(
    r"thread=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
RELAY_MARKERS = ("接力提示词", "flow-boot.py", "--intent")


BOARD_MARKERS = ("任务状态看板", "当前聚焦待办")


def board_visible(reply: str) -> bool:
    """上一轮对外回复里有没有贴收工看板。

    用户反馈（2026-09-25）：「现在的所有会话都不给我汇报，这个任务汇报做不做、
    也不给我打印这个任务看板」。漏贴看板此前**没有任何机检**——`flow-boot.py` 只查
    「查无交付回执」，回执有但回复没贴就无声无息。这里复用与接力提示词同一套观测量
    （`task_complete.last_agent_message`），把「漏贴」变成下一轮开工能被点名的事实。
    """
    return bool(reply) and all(marker in reply for marker in BOARD_MARKERS)


def relay_prompt_visible(reply: str) -> bool:
    """回复里是否真的出现了接力提示词（用户要「在对话框上打印出来再结束」）。"""
    return bool(reply) and all(marker in reply for marker in RELAY_MARKERS)


def active_queue(project: Path | None) -> dict[str, list[str]]:
    """读 plan.md 活跃区，按状态分组（多任务并行时提示词必须交代队列）。"""
    queue: dict[str, list[str]] = {"todo": [], "blocked": [], "pending": []}
    if project is None:
        return queue
    plan = Path(project) / "flow" / "plan.md"
    if not plan.is_file():
        return queue
    bucket = {" ": "todo", "!": "blocked", "-": "pending"}
    for line in plan.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped.startswith(("- ", "* ")):
            continue
        match = PLAN_ITEM_RE.match(stripped)
        if not match:
            continue
        key = bucket.get(match.group(1))
        if not key:
            continue
        queue[key].append(match.group(2).strip())
    return queue


def resolve_ticket(project: Path | None, intent: str, explicit: str = "") -> tuple[str, bool]:
    """定「本次要接的那张卡」。返回 (ticket, 卡是否存在)。

    不再从顶部交接棒标题猜：并行项目里顶部常属于**另一张卡**，猜错的代价是新会话
    去干别人的任务；顶部卡刚归档时更会给出**不存在的路径**（2026-09-24 实测）。
    优先级：显式 --ticket > 活跃区里与 --intent 匹配的卡 > 空（不猜）。
    """
    if project is None:
        return explicit, False
    root = Path(project)
    if explicit:
        return explicit, (root / "flow" / "tasks" / f"{explicit}.md").is_file()
    queue = active_queue(root)
    # 先看活跃区条目里有没有直接出现 ticket，再看意图与条目文字的包含关系。
    for item in queue["todo"] + queue["pending"] + queue["blocked"]:
        match = TICKET_IN_TITLE_RE.search(item.split("thread=")[0])
        if match and match.group(1) in intent:
            return match.group(1), True
    if intent:
        for item in queue["todo"] + queue["pending"] + queue["blocked"]:
            match = TICKET_IN_TITLE_RE.search(item.split("thread=")[0])
            if match and text_overlap(intent, item):
                return match.group(1), True
    # 意图里**显式点名**了某个编号时，就只用它：哪怕它已归档，也只照实说「该卡不在活跃区」，
    # 绝不用别的卡兜底（2026-09-25 实测：新手会因此被带到另一张卡上开工）。
    if intent:
        explicit_hits = TICKET_IN_TITLE_RE.findall(intent.split("thread=")[0])
        for hit in explicit_hits:
            if any(hit in item for item in queue["todo"] + queue["pending"] + queue["blocked"]):
                return hit, True
        if explicit_hits:
            return explicit_hits[0], False
    # 收工交接的主战场：卡已转入 `[-]` 待验收、活跃区清空。此时仍必须能认出它
    # （2026-09-25 实测：只看活跃区 → 提示词永远写「未指定」，用户读成「没交接清楚」）。
    pending = queue["pending"]
    if intent:
        for item in pending:
            match = TICKET_IN_TITLE_RE.search(item.split("thread=")[0])
            if match and text_overlap(intent, item):
                return match.group(1), True
    if len(pending) == 1:
        match = TICKET_IN_TITLE_RE.search(pending[0].split("thread=")[0])
        if match:
            return match.group(1), True
    return "", False


def _card_field(project: Path | None, ticket: str, *names: str) -> str:
    """从任务卡里取字段（goal/objective/acceptance 等）。"""
    if project is None or not ticket:
        return ""
    card = Path(project) / "flow" / "tasks" / f"{ticket}.md"
    if not card.is_file():
        return ""
    values: dict[str, str] = {}
    for line in card.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            values[key.strip().lower()] = value.strip()
    for name in names:
        if values.get(name):
            return values[name]
    return ""


def card_objective(project: Path | None, ticket: str) -> str:
    return _card_field(project, ticket, "goal", "objective")


def acceptance_of(project: Path | None, ticket: str) -> str:
    return _card_field(project, ticket, "acceptance")


def handoff_fields(project: Path | None) -> dict[str, str]:
    """顶部交接棒的结构化字段 + 来源会话 + 标题（接力提示词的「交接来源/任务说明/下一步」来源）。"""
    info = {"title": "", "thread": "", "现状": "", "还剩": "", "卡在哪": "", "下一步": "", "台账": ""}
    if project is None:
        return info
    progress = Path(project) / "flow" / "进展.md"
    if not progress.is_file():
        return info
    lines = progress.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(("## ", "### "))), None)
    if start is None:
        return info
    info["title"] = lines[start].strip()
    match = HANDOFF_THREAD_RE.search(lines[start])
    if match:
        info["thread"] = match.group(1).lower()
    for line in lines[start + 1:]:
        if line.startswith(("## ", "### ")):
            break
        stripped = line.strip().lstrip("-* ").strip()
        for field in ("来源会话", "现状", "还剩", "卡在哪", "下一步", "台账"):
            if stripped.startswith(f"{field}：") or stripped.startswith(f"{field}:"):
                info[field] = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
        if not info["thread"]:
            match = HANDOFF_THREAD_RE.search(line)
            if match:
                info["thread"] = match.group(1).lower()
    return info


def pending_specs(project: Path | None, ticket: str) -> list[str]:
    """台账里还没回收的规格点编号（提示词必须让新会话知道还剩多少）。"""
    if project is None or not ticket:
        return []
    ledger = Path(project) / "flow" / "specs" / f"{ticket}.md"
    if not ledger.is_file():
        return []
    pending: list[str] = []
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
        match = SPEC_LINE_RE.match(line)
        if match and match.group(1) != "x":
            pending.append(f"{match.group(2)} {match.group(3)}".strip())
    return pending


def text_overlap(intent: str, item: str) -> bool:
    """意图与条目是否有足够重叠（粗粒度，够用即可）。"""
    tokens = [tok for tok in re.split(r"[\s，,。；;：:/|（）()\[\]【】]+", intent) if len(tok) >= 2]
    return sum(1 for tok in tokens if tok in item) >= 1


def handoff_prompt(
    intent: str,
    report: dict,
    project: Path | None = None,
    ticket: str = "",
    work_root: str = "",
) -> str:
    """生成给新会话的接力提示词。

    多任务/多工作区项目的硬要求（2026-09-25，zhengjie-hrm 主仓 13 张并行卡 + 3 个 worktree）：
      - **显式交接身份**：ticket 由调用方给出或按 intent 从活跃区匹配，绝不从顶部交接棒标题猜
        （顶部常属于另一张卡；那张卡刚归档时还会给出不存在的路径）；
      - **卡存在性校验**：卡不在 <工作根>/flow/tasks/ 就照实说，并列出活跃区候选；
      - **并行队列与阻塞项**：把活跃 [ ] 队列与 [!] 阻塞一并交代，新会话才知道自己在哪条线上；
      - **分端/主仓分工**：写清工作根，并提示分端在 worktree、主仓只做共享合并。
    """
    root = str(Path(work_root).resolve()) if work_root else (
        str(Path(project).resolve()) if project is not None else "<工作根>"
    )
    resolved, exists = resolve_ticket(project, intent, ticket)
    queue = active_queue(project)
    lines = [
        "继续执行 project-flow 任务。",
        f"工作根：{root}",
        "（若当前 cwd 不是这个工作根，先 `cd` 过去再执行下一条；不要在别的 checkout 上开工）",
        "",
    ]
    fields = handoff_fields(project)
    source_thread = fields["thread"] or (str(report.get("thread_id") or "").strip())
    pending = pending_specs(project, resolved)
    if resolved and exists:
        lines += [
            "—— 交接来源 ——",
            f"来源会话：thread={source_thread or '（未声明）'}",
            f"来源任务卡：{resolved}",
            f"来源交接棒：{fields['title'] or '（进展.md 顶部无交接棒）'}",
            f"台账：{root}/flow/specs/{resolved}.md（未回收 {len(pending)} 条）",
            "",
            "—— 任务说明 ——",
            f"- 这是什么：{card_objective(project, resolved) or '（任务卡缺 objective）'}",
            f"- 当前状态：{fields['现状'] or '（交接棒未写「现状」）'}",
            f"- 还剩：{fields['还剩'] or '（交接棒未写「还剩」）'}",
            f"- 卡在哪：{fields['卡在哪'] or '（交接棒未写「卡在哪」）'}",
            "",
            "—— 下一步 ——",
            f"- 第一件事：{fields['下一步'] or '按台账未回收项继续'}",
            f"- 验收标准：{acceptance_of(project, resolved) or '（任务卡缺 acceptance）'}",
        ]
        if pending:
            lines.append("- 未回收规格点（只做这些）：" + "；".join(pending[:5]))
        else:
            lines.append("- 未回收规格点：无（台账已全绿）；如无新指令，本卡只剩人工验收")
        lines += [
            "",
            "请先按硬首动运行：",
            f'python3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent "{intent}"',
            "",
            "然后只读取（都在上面的工作根下）：",
            f"- {root}/flow/plan.md 当前聚焦 [ ]/[✕]",
            f"- {root}/flow/进展.md 顶部一条",
            f"- 本次任务卡：{root}/flow/tasks/{resolved}.md",
            f"- 规格点台账：{root}/flow/specs/{resolved}.md（只做状态不是 [x] 的规格点）",
            f"- 与当前任务类型匹配的 {root}/flow/规范/*.md",
        ]
    elif resolved:
        lines += [
            # 不写字面路径：契约要求「已归档/不存在的卡不得给出死路径」（见 test-relay-multi-task）。
            f"本次交接身份：{resolved}（**该卡不在活跃区**，可能已归档——请勿按这张卡施工）",
            "请先按硬首动运行：",
            f'python3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent "{intent}"',
            "",
            "然后从下面的活跃区候选里选一张（或按用户本轮指令指定）：",
        ]
    else:
        lines += [
            "本次交接身份：未指定（未从 --ticket 或活跃区匹配到卡，请勿凭顶部交接棒猜）",
            "请先按硬首动运行：",
            f'python3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent "{intent}"',
            "",
            f"然后只读取（都在上面的工作根下）：{root}/flow/plan.md 与 {root}/flow/进展.md 顶部一条，",
            "再从下面的活跃区候选里确认本次要做的那张卡：",
        ]
    if not (resolved and exists):
        for item in queue["todo"][:6]:
            lines.append(f"- [ ] {item[:110]}")
        if not queue["todo"]:
            lines.append("- 活跃区为空：请先按 SDD 在 flow/plan.md 登记原子任务")

    if queue["todo"]:
        lines += ["", f"并行队列（本工作根 plan.md 活跃 [ ]，共 {len(queue['todo'])} 张）："]
        lines += [f"- {item[:110]}" for item in queue["todo"][:6]]
    if queue["blocked"]:
        lines += ["", "阻塞项（[!]，不要撞）："]
        lines += [f"- {item[:110]}" for item in queue["blocked"][:4]]
    if queue["pending"]:
        lines += ["", f"另有 {len(queue['pending'])} 张 [-] 待人工验收：不要重跑。"]

    lines += [
        "",
        "分工边界：主仓只做共享文件与合并窗口；分端在各自 worktree 施工，"
        "不要在没有共享锁的情况下改 pages.json / 共享 api 客户端。",
        "",
        "只做上面这条任务卡对应的未回收规格点；不要遍历其它任务卡、其它工作区或历史归档。",
        "",
        "上一会话已触发预算熔断：",
        f"- 单次输入: {report['input_tokens']} tokens",
        f"- 缓存命中: {report['cache_ratio']:.1%}",
        f"- 上下文占用: {report['context_ratio']:.1%}",
        f"- 轮次: {report['rounds']}，工具调用: {report['tool_calls']}",
        "",
        "请以磁盘真实状态为唯一真相源，继续下一张活跃任务卡；不要复读历史聊天，不要读取 history/ 或 trash/，完成后写入 flow/进展.md 顶部交接棒。",
        "",
        "本会话收尾必须先落盘 SDD 蒸馏交接棒 + 规格点台账，结构如下：",
            "",
        HANDOFF_TEMPLATE,
        "",
        SPEC_LEDGER_TEMPLATE,
            "",
        "硬规则：交接棒与汇报只写「规格点 / 待办 / 证据 / 下一步」，"
        "禁止把用户消息原样贴进来——原样摘抄既不是需求点也不是规格点，只会让新会话重读全部历史。",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--thread-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    parser.add_argument(
        "--intent",
        default="",
        help=(
            "本轮任务摘要。""--print-relay"" 时用它覆盖提示词里的 --intent——"
            "回执里存的是「触发熔断那次开工的意图」，直接粘给新会话会把旧意图当任务。"
        ),
    )
    parser.add_argument("--project", default=".", help="项目根目录（写熔断回执用）")
    parser.add_argument(
        "--ticket",
        default="",
        help="本次交接的任务编号（显式交接身份；不传则按 --intent 从活跃区匹配，绝不从顶部交接棒猜）",
    )
    parser.add_argument("--work-root", default="", help="工作根绝对路径（分端 worktree 场景必须显式给出）")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--guard",
        action="store_true",
        help="中段复查模式：只在超线时输出，供长 turn 内周期性自检（不装 Hook 的替代）",
    )
    parser.add_argument(
        "--sessions-root",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="只读模式：不写熔断回执、不写检查点（供外部心跳/巡检调用）",
    )
    parser.add_argument(
        "--print-relay",
        action="store_true",
        help="只打印可复制的接力提示词（优先取最近熔断回执里存的那份），不判级、不写回执",
    )
    args = parser.parse_args()

    if args.print_relay:
        # 闭环缺口修复（2026-09-23 ATDD 发现）：--print-relay 曾经要求先解析到 session，
        # 解析不到就直接返回——而「换线程/会话已归档/新会话想拿回提示词」正是它的主用途。
        # 现在只要有熔断回执就先把提示词交出来，会话解析失败只作为附注。
        receipt, data = latest_stop_receipt(Path(args.project))
        stored = str(data.get("handoff_prompt") or "").strip()
        if args.intent and stored:
            stored = re.sub(
                r'(--intent\s+")[^"]*(")',
                lambda m: m.group(1) + args.intent + m.group(2),
                stored,
            )
        if not stored and receipt is not None:
            # 降级：回执存在但没带 handoff_prompt（老版本写的回执）→ 用当前会话实时生成一份，
            # 而不是直接说「没有回执」。ATDD 用例 4 就是踩到这条。
            sessions_for_prompt = find_session_files(args.thread_id, args.sessions_root)
            if sessions_for_prompt:
                stored = handoff_prompt(
                    args.intent or DEFAULT_INTENT,
                    summarize_thread(sessions_for_prompt),
                    Path(args.project),
                    ticket=args.ticket,
                    work_root=args.work_root,
                )
                print("project-flow 接力提示词（复制给新会话）")
                print(stored)
                print(f"\n- 来源：{receipt}（{data.get('stopped_at', '')}）｜回执缺 handoff_prompt，已按当前会话实时生成")
                return 0
        if stored:
            print("project-flow 接力提示词（复制给新会话）")
            print(stored)
            print(f"\n- 来源：{receipt}（{data.get('stopped_at', '')}）")
            return 0
        print("project-flow 接力提示词: 该项目没有熔断回执，且当前会话解析失败")
        print(f"- 项目：{Path(args.project).resolve()}")
        print(f"- thread-id：{args.thread_id or '（未提供）'}")
        print("- 先跑一次带 --intent 的 flow-boot.py，或确认 CODEX_THREAD_ID 存在。")
        return 0
    if not args.thread_id:
        print("project-flow 预算: 无法定位当前会话（缺少 CODEX_THREAD_ID）")
        return 0
    sessions = find_session_files(args.thread_id, args.sessions_root)
    if not sessions:
        print(f"project-flow 预算: 未找到 session jsonl: {args.thread_id}")
        return 0

    report = summarize_thread(sessions)
    report["session_file"] = str(sessions[0])
    # 第 3 点：提示词是否已出现在那一轮的对外回复里。放进报告，外部心跳才能体检。
    reply = last_visible_reply(sessions)
    report["relay_prompt_in_reply"] = relay_prompt_visible(reply)
    report["board_in_reply"] = board_visible(reply)
    prompt = handoff_prompt(
        args.intent or DEFAULT_INTENT,
        report,
        Path(args.project),
        ticket=args.ticket,
        work_root=args.work_root,
    )
    if args.print_relay:
        # 「要求交接却没有交接提示词」的正面修复：无论当前会话判级如何，
        # 先把要交给新会话的那段话原样打出来。
        receipt, data = latest_stop_receipt(Path(args.project))
        stored = str(data.get("handoff_prompt") or "").strip()
        if args.intent and stored:
            # 实测坑（2026-09-23）：回执里那条 --intent 是「触发熔断那次开工的意图」。
            # 单纯索取提示词时它毫无意义，直接粘给新会话会把旧意图当任务。
            # 所以允许用「同一个 --intent」覆盖打印出来的那条，不再多造一个参数。
            stored = re.sub(
                r'(--intent\s+")[^"]*(")',
                lambda m: m.group(1) + args.intent + m.group(2),
                stored,
            )
        print("project-flow 接力提示词（复制给新会话）")
        print(stored or prompt)
        if receipt is not None:
            print(f"\n- 来源：{receipt}（{data.get('stopped_at', '')}）")
        else:
            print("\n- 来源：本次会话实时计算（尚无熔断回执）")
        return 0
    # 熔断回执只由「开工那一次预算判定」写：中段复查每 50 次工具调用跑一次，
    # 若也写回执，flow/budget/ 会被重复回执刷爆，「最近一次 STOP」判定随即失真。
    if report["level"] == "STOP" and not args.guard and not args.read_only:
        receipt = persist_stop(Path(args.project), args.thread_id, report, prompt)
        if receipt is not None:
            report["stop_receipt"] = str(receipt)
    if args.guard:
        # 中段复查：一个 turn 内跑几百次工具调用时，开工那一次预算判定早就过期了。
        # 无 Hook 的前提下，只能把「复查」做成一条可以被明确调用的命令。
        checkpoint = Path(args.project) / "flow" / BUDGET_DIR / GUARD_FILE
        if checkpoint.parent.is_dir() and not args.read_only:
            checkpoint.write_text(
                json.dumps(
                    {
                        "operation": "guard_checkpoint",
                        "thread_id": args.thread_id,
                        "checked_at": datetime.now().isoformat(timespec="seconds"),
                        "tool_calls": report["tool_calls"],
                        "level": report["level"],
                        "input_tokens": report["input_tokens"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        if report["level"] == "OK":
            print("project-flow 中段复查 [OK]：可继续，但每 50 次工具调用再复查一次。")
            return 0
        print(f"project-flow 中段复查 [{report['level']}]：立即停止扩展实现。")
        for reason in report["reasons"]:
            print(f"- {reason}")
        print("- 动作：把规格点与待办蒸馏进 flow/进展.md 顶部交接棒 + flow/specs/<ticket>.md，")
        print("  逐条回收状态与证据，然后开新会话；禁止在本会话继续堆上下文。")
        # 用户反馈「要求交接却没有交接提示词」：中段复查是贴了纠偏词后最常走的路径，
        # 必须在这里就把可复制的提示词给全，而不是只给一句「动作」。
        print("\nproject-flow 接力提示词（复制给新会话）")
        print(prompt)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["level"] == "STOP" else 0

    file_note = ""
    if len(sessions) > 1:
        file_note = f"（该 thread 共 {len(sessions)} 个 rollout 文件：轮次/调用量累加，历史峰值仅作证据）"
    print(f"project-flow 预算 [{report['level']}]: {sessions[0]}{file_note}")
    print(
        f"- 单次输入 {report['input_tokens']} / 窗口 {report['context_window']} "
        f"({report['context_ratio']:.1%}), 缓存 {report['cache_ratio']:.1%}, "
        f"轮次 {report['rounds']}, 工具调用 {report['tool_calls']}"
    )
    for reason in report["reasons"]:
        print(f"- {reason}")
    if report["level"] == "WARN":
        print("\nproject-flow 预算 WARN 处置（柔性，不阻断）")
        print("- 先做 SDD 拆卡：任务偏大时回上游 flow/plan.md 把本卡拆成原子卡，不要靠加大读取硬推。")
        print("- 收尾前把规格点/待办写进 flow/specs/<ticket>.md，达到熔断线直接交接，不必撑到自动压缩。")
    if report["level"] in {"WARN", "STOP"}:
        # 用户反馈：「应该先在对话框上打印出交接提示词再结束，而不是直接熔断」。
        # 提示词光在工具输出里不够——它必须出现在那一轮的对外回复里。
        if not report.get("relay_prompt_in_reply"):
            print("\nproject-flow 上轮回复缺失接力提示词（必须在本轮回复里原样贴出）")
            print("- 判据：task_complete.last_agent_message 里必须同时出现「接力提示词」、"
                  "`flow-boot.py` 与 `--intent`。")
            print("- 以下整段必须原样复制进你的回复，再结束本轮；只写「已熔断」不算交接。")
        print("\nproject-flow 接力提示词")
        print(prompt)
    # 只要项目里有交付回执，上一轮的对外回复就必须贴出看板（三段契约之一）。
    # 没有回执时不判——还没交付过，谈不上漏贴。
    deliveries_dir = Path(args.project) / "flow" / DELIVERIES_DIR
    has_delivery = deliveries_dir.is_dir() and any(deliveries_dir.glob("*.json"))
    if has_delivery and not report.get("board_in_reply"):
        print("\nproject-flow 上轮回复缺失任务看板（本轮必须把三段原样贴出）")
        print("- 判据：task_complete.last_agent_message 里必须同时出现「任务状态看板」与"
              "「当前聚焦待办」；只有回执落盘、回复里没贴，等于没交付。")
        print("- 收工时把 `flow-deliver.py` 输出的「任务状态看板 / 本轮工作汇报 / 交付验收卡」"
              "三段**原样**复制进回复；禁止只写摘要，禁止用 `| tail -N` 把三段截掉。")
    if report["level"] == "STOP":
        print("\nproject-flow 柔性阻塞：本轮只允许「交接落盘」，禁止登记新意图与业务施工")
        print("- 必须落盘：flow/进展.md 顶部 SDD 蒸馏交接棒 + flow/specs/<ticket>.md 规格点台账")
        print("- 核销方式：补完交接棒后新会话开工，flow-boot.py 自动核销本次熔断回执")
    if report.get("stop_receipt"):
        print(f"\n- 熔断回执：{report['stop_receipt']}（下一轮开工校验交接棒是否补上）")
    return 1 if report["level"] == "STOP" else 0


if __name__ == "__main__":
    raise SystemExit(main())
