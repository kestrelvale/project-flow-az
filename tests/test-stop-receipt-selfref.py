#!/usr/bin/env python3
"""熔断回执「自引用」不得永久阻塞接手的新会话。

事故（2026-09-24 实测 zhengjie-hrm wt-p4，thread 01a0c1cd）：
当事会话先落交接棒、后由开工时的预算检查写回执，于是回执里的 `handoff_head`
快照 == 它自己刚写的那条标题；而 `read_pending_stop` 的核销判据之一是
「顶部标题 != 快照」，加上兜底扫描被 `owner != declared` 挡住（此时 declared == owner），
这条回执就永远核销不掉 —— 当事会话之外的任何新会话只要接手就被判柔性阻塞。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "scripts" / "flow-boot.py"
OWNER = "01a0c1cd-a264-7321-8779-8440e6de59ac"
NEW = "01a0cf2d-89f3-7ae1-a981-51662657ac2e"
OLD_HEAD = "## 2026-09-22 · 旧交接棒 · T1"
NEW_HEAD = (
    "## 2026-09-23 · T1 · 交接棒（SDD 蒸馏） · thread=01a0c1cd-a264-7321-8779-8440e6de59ac"
)
NEW_BODY = "\n".join(
    [
        NEW_HEAD,
        "- 规格点(SPE)：SPE-1 登录四态补齐 —— 证据：pytest exit 0",
        "- 待办(TODO)：- [x] SPE-1",
        "- 现状：已交接",
        "- 还剩：SPE-2",
        "- 卡在哪：无",
        "- 下一步：开新会话按未回收规格点继续",
    ]
)


def build(root: Path) -> Path:
    flow = root / "flow"
    for name in ("tasks", "history", "trash", "budget", "gc/receipts"):
        (flow / name).mkdir(parents=True, exist_ok=True)
    (flow / "规范").mkdir()
    (flow / "规范" / "VERSION").write_text(
        (ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (flow / "plan.md").write_text(
        "# Plan\n## 当前聚焦待办 (P0)\n- [ ] T1 [登录状态修复] 修正登录失效\n", encoding="utf-8"
    )
    for name in ("charter.md", "decisions.md", "踩坑记录.md"):
        (flow / name).write_text("", encoding="utf-8")
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
    return flow


def receipt(name: str, head: str) -> Path:
    path = Path(name)
    path.write_text(
        json.dumps(
            {
                "operation": "budget_stop",
                "thread_id": OWNER,
                "input_tokens": 643_191,
                "rounds": 10,
                "tool_calls": 369,
                "reasons": ["上下文占用 67.7%"],
                "handoff_head": head,
                "handoff_prompt": "继续执行 project-flow 任务…",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def boot(flow: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(BOOT),
            str(flow.parent),
            "--intent",
            "T1 登录状态修复",
            "--skip-budget",
            "--thread-id",
            NEW,
        ],
        text=True,
        capture_output=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        flow = build(Path(tmp))
        receipts = flow / "budget"

        # 时序 1（本缺陷）：18:05 落旧交接棒 → 18:06 回执①（快照=旧标题）
        #                  18:07 当事会话写新交接棒 → 18:08 回执②（快照==新标题）
        # 回执② 必须判为已核销：交接棒已经落盘，只是快照撞上了它自己。
        old = receipt(receipts / "20260923-180607-stop.json", OLD_HEAD)
        (flow / "进展.md").write_text(NEW_BODY + "\n\n" + OLD_HEAD + "\n- 现状: 旧\n", encoding="utf-8")
        receipt(receipts / "20260923-180810-stop.json", NEW_HEAD)

        taken_over = boot(flow)
        assert "上一轮预算 STOP 未交接" not in taken_over.stdout, taken_over.stdout
        assert "【柔性阻塞】" not in taken_over.stdout, taken_over.stdout

        # 时序 2（负向，fail-closed 不得放宽）：当事会话熔断后**没写新交接棒**，
        # 顶部仍是它上一轮的合规交接棒 → 快照 == 顶部标题 == 上一条回执快照 → 继续阻塞。
        old.unlink()
        (receipts / "20260923-180810-stop.json").unlink()
        receipt(receipts / "20260923-190000-stop.json", NEW_HEAD)
        receipt(receipts / "20260923-190500-stop.json", NEW_HEAD)

        still_blocked = boot(flow)
        assert "上一轮预算 STOP 未交接" in still_blocked.stdout, still_blocked.stdout
        assert "【柔性阻塞】" in still_blocked.stdout, still_blocked.stdout
    print("PASS: self-referencing stop receipts clear only when a new handoff actually landed")


if __name__ == "__main__":
    main()
