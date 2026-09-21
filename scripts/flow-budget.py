#!/usr/bin/env python3
"""会话预算门禁：从当前 Codex session 读取真实 token 用量并输出接力提示。"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

WARN_RATIO = 0.75
STOP_RATIO = 0.90
MAX_INPUT_TOKENS = 300_000
MAX_ROUNDS = 25
MAX_TOOL_CALLS = 100


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
    if ratio >= STOP_RATIO or input_tokens >= MAX_INPUT_TOKENS:
        level = "STOP"
    elif ratio >= WARN_RATIO:
        level = "WARN"
    if len(rounds) >= MAX_ROUNDS:
        level = "STOP"
    elif len(rounds) >= int(MAX_ROUNDS * 0.8) and level == "OK":
        level = "WARN"
    if tool_calls >= MAX_TOOL_CALLS:
        level = "STOP"
    if input_tokens > context_window:
        reasons.append(f"单次输入 {input_tokens} 已超过记录的上下文窗口 {context_window}")
    if ratio >= WARN_RATIO:
        reasons.append(f"上下文占用 {ratio:.1%}")
    if len(rounds) >= MAX_ROUNDS:
        reasons.append(f"轮次 {len(rounds)} >= {MAX_ROUNDS}")
    if tool_calls >= MAX_TOOL_CALLS:
        reasons.append(f"工具调用 {tool_calls} >= {MAX_TOOL_CALLS}")
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
            "- 与当前任务类型匹配的 flow/规范/*.md",
            "",
            "上一会话已触发预算熔断：",
            f"- 单次输入: {report['input_tokens']} tokens",
            f"- 缓存命中: {report['cache_ratio']:.1%}",
            f"- 上下文占用: {report['context_ratio']:.1%}",
            f"- 轮次: {report['rounds']}，工具调用: {report['tool_calls']}",
            "",
            "请以磁盘真实状态为唯一真相源，继续下一张活跃任务卡；不要复读历史聊天，不要读取 history/ 或 trash/，完成后写入 flow/进展.md 顶部交接棒。",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--thread-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    parser.add_argument("--intent", default="继续当前 project-flow 活跃任务")
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
    if report["level"] in {"WARN", "STOP"}:
        print("\nproject-flow 接力提示词")
        print(handoff_prompt(args.intent, report))
    return 1 if report["level"] == "STOP" else 0


if __name__ == "__main__":
    raise SystemExit(main())
