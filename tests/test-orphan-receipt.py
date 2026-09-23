#!/usr/bin/env python3
"""孤儿熔断回执（owner 会话已消失）必须能被显式作废：列候选 / 留痕 / 无参不改行为。

事故：`flow/budget/*-stop.json` 的 owner 会话消失后，其后每个新会话开工都吃
「上一轮预算 STOP 未交接」柔性阻塞，而当事会话永远不会再来核销。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "scripts" / "flow-boot.py"
DEAD = "01a0c297-b8e5-7000-8000-00000000dead"
LIVE = "01a0cf2d-89f3-7ae1-a981-51662657ac2e"
DEAD_RECEIPT = "20260923-231041-stop.json"
LIVE_RECEIPT = "20260923-233907-stop.json"
OLD_HEAD = "## 2026-09-22 · 旧交接棒 · T1"


def receipt(thread_id: str) -> str:
    return json.dumps(
        {
            "operation": "budget_stop",
            "thread_id": thread_id,
            "input_tokens": 300_000,
            "rounds": 23,
            "tool_calls": 160,
            "reasons": ["工具调用 160 >= 160"],
            "handoff_head": OLD_HEAD,
        },
        ensure_ascii=False,
    )


def build(root: Path) -> tuple[Path, Path]:
    flow = root / "flow"
    for name in ("tasks", "history", "trash", "gc/receipts", "budget"):
        (flow / name).mkdir(parents=True, exist_ok=True)
    (flow / "规范").mkdir()
    (flow / "规范" / "VERSION").write_text(
        (ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (flow / "plan.md").write_text(
        "\n".join(
            [
                "# Plan",
                "## 当前聚焦待办 (P0)",
                "- [ ] T1 [登录状态修复] 修正登录失效",
            ]
        ),
        encoding="utf-8",
    )
    for name in ("charter.md", "decisions.md", "踩坑记录.md"):
        (flow / name).write_text("", encoding="utf-8")
    (flow / "进展.md").write_text(f"{OLD_HEAD}\n- 现状: 旧\n", encoding="utf-8")
    (flow / "tasks" / "T1-login.md").write_text(
        "\n".join(
            [
                "ticket_id: T1",
                "objective: 修正登录失效",
                "mode: execute",
                "method: SDD,TDD,ATDD,BDD",
                "scope: 输入=登录请求；输出=有效令牌；边界=不改密码策略",
                "write_whitelist: src/auth.ts,tests/auth.test.ts",
                "verify_command: npm test -- auth",
                "acceptance: Given 有效账号，When 登录，Then 返回有效令牌",
            ]
        ),
        encoding="utf-8",
    )
    sessions = root / "sessions"
    (sessions / "2026" / "09" / "23").mkdir(parents=True)
    rollout = sessions / "2026" / "09" / "23" / f"rollout-2026-09-23T23-39-07-{LIVE}.jsonl"
    rollout.write_text("", encoding="utf-8")
    return flow, sessions


def write_receipts(flow: Path, *pairs: tuple[str, str]) -> None:
    for path in (flow / "budget").glob("*-stop.json"):
        path.unlink()
    for name, owner in pairs:
        (flow / "budget" / name).write_text(receipt(owner), encoding="utf-8")


def boot(root: Path, sessions: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(BOOT),
            str(root),
            "--intent",
            "登录状态修复",
            "--skip-budget",
            "--thread-id",
            LIVE,
            "--sessions-root",
            str(sessions),
            *extra,
        ],
        text=True,
        capture_output=True,
    )


def ledgers(flow: Path) -> list[dict]:
    found = []
    for path in sorted((flow / "gc" / "receipts").glob("*.json")):
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return found


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flow, sessions = build(root)

        # 孤儿回执（owner 会话已消失）单条在库：无参数开工必须被它阻塞。
        write_receipts(flow, (DEAD_RECEIPT, DEAD))

        # SPE-3 前置：无显式参数时，孤儿回执照旧阻塞（这是本次要解开的症状）。
        blocked = boot(root, sessions)
        assert "上一轮预算 STOP 未交接" in blocked.stdout, blocked.stdout
        assert "【柔性阻塞】" in blocked.stdout, blocked.stdout

        # SPE-1：命令列出候选孤儿回执（只列，不改）。
        listed = boot(root, sessions, "--void-stale-receipt")
        assert listed.returncode == 0, (listed.returncode, listed.stderr)
        assert DEAD_RECEIPT in listed.stdout, listed.stdout

        # SPE-3：只列候选**不改任何东西** —— 回执还在，没写留痕，开工照旧阻塞。
        assert (flow / "budget" / DEAD_RECEIPT).is_file()
        assert not ledgers(flow), ledgers(flow)
        still_blocked = boot(root, sessions)
        assert "上一轮预算 STOP 未交接" in still_blocked.stdout, still_blocked.stdout

        # SPE-3：不存在的名字拒绝作废（没有显式命中的候选就不动手）。
        bogus = boot(root, sessions, "--void-stale-receipt", "--confirm", "20200101-000000-stop.json")
        assert bogus.returncode != 0, bogus.stdout
        assert (flow / "budget" / DEAD_RECEIPT).is_file()
        assert not ledgers(flow), ledgers(flow)

        # SPE-2：显式作废 -> 写 flow/gc/receipts/ 留痕（保留原回执内容）+ 开工不再阻塞。
        voided = boot(root, sessions, "--void-stale-receipt", "--confirm", DEAD_RECEIPT)
        assert voided.returncode == 0, (voided.returncode, voided.stderr)
        assert not (flow / "budget" / DEAD_RECEIPT).exists()
        entries = ledgers(flow)
        assert len(entries) == 1, entries
        assert entries[0]["operation"] == "receipt_void", entries[0]
        assert entries[0]["thread_id"] == DEAD, entries[0]
        assert entries[0]["original"]["handoff_head"] == OLD_HEAD, entries[0]
        assert entries[0]["voided_receipt"] == DEAD_RECEIPT, entries[0]

        released = boot(root, sessions)
        assert "上一轮预算 STOP 未交接" not in released.stdout, released.stdout
        assert "【柔性阻塞】" not in released.stdout, released.stdout

        # SPE-1 边界：活会话的回执不得被列为候选，显式点名也拒绝作废。
        write_receipts(flow, (DEAD_RECEIPT, DEAD), (LIVE_RECEIPT, LIVE))
        relisted = boot(root, sessions, "--void-stale-receipt")
        assert DEAD_RECEIPT in relisted.stdout, relisted.stdout
        assert LIVE_RECEIPT not in relisted.stdout, relisted.stdout
        refused = boot(root, sessions, "--void-stale-receipt", "--confirm", LIVE_RECEIPT)
        assert refused.returncode != 0, refused.stdout
        assert (flow / "budget" / LIVE_RECEIPT).is_file()
        assert len(ledgers(flow)) == 1, ledgers(flow)
    print("PASS: orphan stop receipts list, refuse, and void with a ledger")


if __name__ == "__main__":
    main()
