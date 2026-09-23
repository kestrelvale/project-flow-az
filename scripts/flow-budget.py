#!/usr/bin/env python3
"""会话预算门禁：从当前 Codex session 读取真实 token 用量并输出接力提示。"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

# 阈值按实测标定（2026-09-23 取证 8 个分端会话 rollout，窗口 950k）：
#   - 首个「用户消息回放块」出现在单次输入 556166 / 574491 / 608167；
#   - 压缩安装成功样本在 882k，全程最高 996k；
#   - 工具调用阈值 100 曾在单次输入仅 38% 时误报 STOP（P4 会话），
#     天天报警却没人执行，等于把熔断降级成噪音。
# 因此 STOP 压到 28 万（≈29%，距压缩区约一半余量），WARN 18 万；
# 轮次与工具调用作为同量级兜底维度，只在 token 维度失效时接棒。
WARN_RATIO = 0.18
STOP_RATIO = 0.29
WARN_INPUT_TOKENS = 180_000
STOP_INPUT_TOKENS = 280_000
WARN_ROUNDS = 15
STOP_ROUNDS = 22
WARN_TOOL_CALLS = 90
STOP_TOOL_CALLS = 150

# 熔断回执目录：STOP 必须落盘，否则交接棒全靠模型自觉。
# 实测 2026-09-21 的 8 个 zhengjie 分端会话：flow-budget 每次都判出 STOP
# （最高累积 371 次工具调用），但 8 个会话里只有 1 个把接力提示词写进过回复，
# 其余直接继续施工到会话结束——触发层正常，强制层缺失。
BUDGET_DIR = "budget"


def top_handoff_head(flow: Path) -> str:
    """取 进展.md 顶部第一条交接记录的标题行。"""
    progress = flow / "进展.md"
    if not progress.is_file():
        return ""
    for line in progress.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("## ") or line.startswith("### "):
            return line.strip()
    return ""


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


def find_session_file(thread_id: str) -> Path | None:
    root = Path.home() / ".codex" / "sessions"
    matches = sorted(root.rglob(f"*{thread_id}*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def summarize(path: Path) -> dict:
    usage = {}
    last_request_usage = {}
    thread_usage_total = {}
    context_window = 0
    rounds: set[str] = set()
    tool_calls = 0
    seen_tool_call_ids: set[str] = set()
    last_event = None

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
    cached = usage.get("cached_input_tokens", 0)
    ratio = input_tokens / context_window if context_window else 0.0
    cache_ratio = cached / input_tokens if input_tokens else 0.0
    level = "OK"
    reasons: list[str] = []
    context_stop = ratio >= STOP_RATIO or input_tokens >= STOP_INPUT_TOKENS
    context_warn = ratio >= WARN_RATIO or input_tokens >= WARN_INPUT_TOKENS
    volume_stop = len(rounds) >= STOP_ROUNDS or tool_calls >= STOP_TOOL_CALLS
    volume_warn = len(rounds) >= WARN_ROUNDS or tool_calls >= WARN_TOOL_CALLS
    if context_stop or volume_stop:
        level = "STOP"
    elif context_warn or volume_warn:
        level = "WARN"
    if input_tokens > context_window:
        reasons.append(f"单次输入 {input_tokens} 已超过记录的上下文窗口 {context_window}")
    if context_stop:
        reasons.append(
            f"上下文占用 {ratio:.1%} / 单次输入 {input_tokens} "
            f"（熔断线 {STOP_INPUT_TOKENS} 或 {STOP_RATIO:.0%}；压缩区实测起于 556k）"
        )
    elif context_warn:
        reasons.append(
            f"上下文占用 {ratio:.1%} / 单次输入 {input_tokens}（接近熔断线，先做 SDD 拆卡）"
        )
    if len(rounds) >= STOP_ROUNDS:
        reasons.append(f"轮次 {len(rounds)} >= {STOP_ROUNDS}")
    elif len(rounds) >= WARN_ROUNDS:
        reasons.append(f"轮次 {len(rounds)} >= {WARN_ROUNDS}")
    if tool_calls >= STOP_TOOL_CALLS:
        reasons.append(f"工具调用 {tool_calls} >= {STOP_TOOL_CALLS}")
    elif tool_calls >= WARN_TOOL_CALLS:
        reasons.append(f"工具调用 {tool_calls} >= {WARN_TOOL_CALLS}")
    if not reasons:
        reasons.append("预算正常")

    return {
        "session_file": str(path),
        "level": level,
        "reasons": reasons,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "cache_ratio": cache_ratio,
        "output_tokens": usage.get("output_tokens", 0),
        "thread_input_tokens": thread_usage_total.get("input_tokens", 0),
        "thread_cached_input_tokens": thread_usage_total.get("cached_input_tokens", 0),
        "context_window": context_window,
        "context_ratio": ratio,
        "rounds": len(rounds),
        "tool_calls": tool_calls,
        "last_event": last_event,
    }


# 交接棒必须是 SDD 蒸馏产物：把用户原话提炼成「要执行的规格点」与「待办清单」。
# 实测 2026-09-21 的 P0/P4 会话：压缩时模型把用户消息原样回放成 12k~29k 字节的
# 复述块当成汇报，既没有规格点也没有销账，新会话只能重读全部历史——熔断白做。
SPEC_LEDGER_TEMPLATE = """### ♻️ 规格点回收台账（每条都要回收，禁止原样照抄用户消息）
- [ ] SPE-1 | <要执行的规格点：可观察的结果> | 证据：
- [ ] SPE-2 | <同上> | 证据：
- [!] SPE-3 | <阻塞规格点> | 证据：<阻塞证据> / 解除条件：<…>"""

HANDOFF_TEMPLATE = """## <日期> · <ticket> · 交接棒（SDD 蒸馏）
- 规格点(SPE)：SPE-1..n —— 只写「要执行的规格」，不抄用户原话
- 待办(TODO)：`- [ ]` 未做 / `- [-]` 进行中 / `- [x]` 完成 / `- [!]` 阻塞；完成项必须带证据
- 现状：<一句话>
- 还剩：<未回收的 SPE 编号，以及为什么没做完>
- 卡在哪：<阻塞 + 解除条件>
- 下一步：<新会话第一件事，含门禁命令>
- 台账：flow/specs/<ticket>.md（未回收项是唯一待办源，已完成项不得重跑）"""


def handoff_prompt(intent: str, report: dict) -> str:
    return "\n".join(
        [
            "继续执行 project-flow 任务，请先按硬首动运行：",
            f'python3 ~/.codex/skills/project-flow-az/scripts/flow-boot.py . --intent "{intent}"',
            "",
            "然后只读取：",
            "- flow/plan.md 当前聚焦 [ ]/[✕]",
            "- flow/进展.md 顶部一条",
            "- 当前任务对应的 flow/tasks/<ticket>.md",
            "- flow/specs/<ticket>.md 里状态不是 [x] 的规格点（只做未回收项）",
            "- 与当前任务类型匹配的 flow/规范/*.md",
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
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--thread-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    parser.add_argument("--intent", default="继续当前 project-flow 活跃任务")
    parser.add_argument("--project", default=".", help="项目根目录（写熔断回执用）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.thread_id:
        print("project-flow 预算: 无法定位当前会话（缺少 CODEX_THREAD_ID）")
        return 0
    session = find_session_file(args.thread_id)
    if session is None:
        print(f"project-flow 预算: 未找到 session jsonl: {args.thread_id}")
        return 0

    report = summarize(session)
    prompt = handoff_prompt(args.intent, report)
    if report["level"] == "STOP":
        receipt = persist_stop(Path(args.project), args.thread_id, report, prompt)
        if receipt is not None:
            report["stop_receipt"] = str(receipt)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["level"] == "STOP" else 0

    print(f"project-flow 预算 [{report['level']}]: {session}")
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
        print("\nproject-flow 接力提示词")
        print(prompt)
    if report["level"] == "STOP":
        print("\nproject-flow 柔性阻塞：本轮只允许「交接落盘」，禁止登记新意图与业务施工")
        print("- 必须落盘：flow/进展.md 顶部 SDD 蒸馏交接棒 + flow/specs/<ticket>.md 规格点台账")
        print("- 核销方式：补完交接棒后新会话开工，flow-boot.py 自动核销本次熔断回执")
    if report.get("stop_receipt"):
        print(f"\n- 熔断回执：{report['stop_receipt']}（下一轮开工校验交接棒是否补上）")
    return 1 if report["level"] == "STOP" else 0


if __name__ == "__main__":
    raise SystemExit(main())
