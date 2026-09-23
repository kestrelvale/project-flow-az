#!/usr/bin/env python3
"""project-flow 预算心跳（外部兜底，不依赖 Codex app 的 automation 工具）。

为什么需要外部心跳：`flow-budget.py` 只在 agent 主动调用时运行。实测 P4 会话在
**同一个 turn 内**跑了 200+ 次工具调用，开工那一次判定（当时仅 38%）早已过期，
一路堆到单次输入 60.8 万、被模型自己「摆烂」暴露。app 侧 automation 需要
`automation_update` 工具（本机不可用），所以用外部计划任务兜底。

能力边界（诚实声明）：外部进程**不能**往会话里插消息——那需要 app 的调度器，
或 app-server 守护进程协议。本心跳能做的是：定期算预算 → 越过线就发系统通知
+ 写告警日志，让「该交接了」在你眼前出现，而不是等下一次开工才发现。

用法：flow-heartbeat.py [--quiet] [--sessions-root PATH] [--hours 4] [--notify]
退出码：0=无告警；1=有会话越过预算线（供 launchd/CI 观测）
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
BUDGET_SCRIPT = SKILL_DIR / "scripts" / "flow-budget.py"
STATE_FILE = Path.home() / ".codex" / "project-flow-heartbeat.json"
LOG_FILE = Path.home() / ".codex" / "project-flow-heartbeat.log"
# 同一会话同一等级 30 分钟内只提醒一次，避免每 15 分钟刷屏。
QUIET_SECONDS = 1800


def project_of(rollout: Path) -> Path | None:
    """从 rollout 的 session_meta.cwd 找到 project-flow 项目根。"""
    cwd = None
    with rollout.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"session_meta"' not in line:
                continue
            try:
                payload = json.loads(line).get("payload") or {}
            except json.JSONDecodeError:
                continue
            cwd = payload.get("cwd")
            break
    if not cwd:
        return None
    for parent in [Path(cwd), *Path(cwd).parents]:
        if (parent / "flow" / "plan.md").is_file():
            return parent
    return None


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    """读-合并-原子写。

    直接用 write_text 会在并发时互相覆盖：`launchctl kickstart -k` 会先杀旧实例，
    实测两个实例交错写把去重表冲成只剩 1 个键 → 同一批会话被反复通知（刷屏）。
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged = load_state()
    merged.update(state)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def thread_id_of(rollout: Path) -> str:
    """rollout-<ISO时间>-<thread_id>[_<续跑会话>].jsonl → 第一个 UUID。

    不能用 split("-", 3)：文件名前缀本身含 `-`（`2026-09-22T20-30-49`），
    按分隔符切会把时间戳片段当成 thread id（实测得到 `23T01-43-20-`）。
    """
    match = re.search(
        r"rollout-[\dT:\-]+-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        rollout.stem,
    )
    return match.group(1) if match else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions-root", type=Path, default=Path.home() / ".codex" / "sessions")
    parser.add_argument("--hours", type=float, default=4.0)
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if not BUDGET_SCRIPT.is_file():
        print(f"flow-heartbeat: 找不到 {BUDGET_SCRIPT}")
        return 0

    cutoff = time.time() - args.hours * 3600
    candidates: list[tuple[Path, str, Path]] = []
    for rollout in args.sessions_root.rglob("rollout-*.jsonl"):
        if rollout.stat().st_mtime < cutoff:
            continue
        project = project_of(rollout)
        if project is None:
            continue
        candidates.append((rollout, thread_id_of(rollout), project))
    if not candidates:
        return 0

    state = load_state()
    alerts: list[str] = []
    now = time.time()
    for rollout, thread_id, project in candidates:
        if not thread_id:
            continue
        result = subprocess.run(
            [
                sys.executable,
                str(BUDGET_SCRIPT),
                "--thread-id",
                thread_id,
                "--project",
                str(project),
                "--json",
                "--read-only",
            ],
            text=True,
            capture_output=True,
        )
        try:
            report = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            continue
        level = report.get("level")
        # level 缺失说明这次没算出来（JSON 解析空/会话找不到），不得当成告警写日志。
        if level not in {"OK", "WARN", "STOP"}:
            continue
        if level == "OK":
            continue
        key = f"{thread_id}:{level}"
        if now - float(state.get(key, 0)) < QUIET_SECONDS:
            continue
        state[key] = now
        alerts.append(
            f"[{level}] {project.name} / {thread_id[:12]} — "
            f"输入 {report.get('input_tokens', 0):,}/{report.get('context_window', 0):,} "
            f"({report.get('context_ratio', 0):.1%})，轮次 {report.get('rounds')}，"
            f"工具调用 {report.get('tool_calls')}；该交接了（写 SDD 蒸馏交接棒 + 规格点台账后开新会话）"
        )

    if alerts:
        save_state(state)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(time.strftime("## %Y-%m-%d %H:%M:%S\n"))
            handle.write("\n".join(f"- {line}" for line in alerts) + "\n")
        if args.notify:
            message = alerts[0].replace('"', "'")[:180]
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{message}" with title "project-flow 预算告警"',
                ],
                capture_output=True,
            )
        if not args.quiet:
            print("\n".join(alerts))
        return 1
    if not args.quiet:
        print(f"flow-heartbeat: 检查 {len(candidates)} 个 project-flow 会话，无告警")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
