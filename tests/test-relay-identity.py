#!/usr/bin/env python3
"""接力提示词必须自带交接身份、任务说明与下一步（否则新会话只能自己猜）。

用户反馈（2026-09-25）：「你连原始的会话 ID 都没有放上去；也没有写清楚这个到底是什么；
下一步需要新会话去交接什么东西、执行什么呀？」

当时的实测输出只有「本次交接身份：未指定」，整段里：
  1) 没有**来源会话 thread id**（回执里有，提示词正文没写）；
  2) 没有一句话说明**这是什么任务、当前什么状态**；
  3) 没有**新会话第一步做什么、验收标准是什么、还剩多少未回收规格点**；
  4) 而且卡一转入 `[-]` 待验收（活跃区清空），ticket 解析恒为「未指定」——
     接力提示词的主战场恰恰是「刚交接完、卡在待验收」的时刻。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET = ROOT / "scripts" / "flow-budget.py"
SRC_THREAD = "01a0cf2d-89f3-7ae1-a981-51662657ac2e"
NEW_THREAD = "ffffffff-0000-4000-8000-0000000000aa"
TICKET = "TASK-DEMO-20260925"
HANDOFF_TITLE = f"## 2026-09-25 · {TICKET} · 交接棒（SDD 蒸馏） · thread={SRC_THREAD}"


def build(root: Path, pending_card: bool = True) -> Path:
    flow = root / "flow"
    for name in ("tasks", "specs", "budget", "deliveries", "history/tasks", "gc/receipts", "规范"):
        (flow / name).mkdir(parents=True, exist_ok=True)
    (flow / "规范" / "VERSION").write_text(
        (ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
    )
    # 卡在 [-] 待验收区：这正是「刚交接完」的真实形态。
    plan_lines = ["# Plan", "## 🎯 当前聚焦待办 (P0)", "- 无"]
    if pending_card:
        plan_lines += [
            "## ⏳ 待人工验收 (Pending Verification)",
            f"- [-] {TICKET} [P0] 等人工验收：把 X 收口（v4.15.18）",
        ]
    (flow / "plan.md").write_text("\n".join(plan_lines) + "\n", encoding="utf-8")
    for name in ("charter.md", "decisions.md", "踩坑记录.md"):
        (flow / name).write_text("", encoding="utf-8")
    (flow / "进展.md").write_text(
        "\n".join(
            [
                HANDOFF_TITLE,
                f"- 来源会话：thread={SRC_THREAD}",
                "- 规格点(SPE)：SPE-1 渲染修复｜SPE-2 机检补齐",
                "- 待办(TODO)：- [x] SPE-1｜- [ ] SPE-2",
                "- 现状：v4.15.18 已推送 origin/main；run-all 21 项 Exit 0。",
                "- 还剩：SPE-2 机检补齐。",
                "- 卡在哪：无。",
                "- 下一步：按台账补 SPE-2，再跑 `bash tests/run-all.sh`。",
                f"- 台账：flow/specs/{TICKET}.md",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (flow / "tasks" / f"{TICKET}.md").write_text(
        "\n".join(
            [
                f"ticket_id: {TICKET}",
                "objective: 把 X 收口：渲染修复与机检补齐",
                "mode: execute",
                "method: SDD,TDD,ATDD,BDD",
                "scope: 输入=x；输出=y；边界=z",
                "write_whitelist: scripts/a.py",
                "verify_command: bash tests/run-all.sh",
                "acceptance: Given x，When y，Then z",
                f"spec_ledger: flow/specs/{TICKET}.md",
            ]
        ),
        encoding="utf-8",
    )
    (flow / "specs" / f"{TICKET}.md").write_text(
        "- [x] SPE-1 | 渲染修复 | 证据：tests/run-all.sh\n"
        "- [ ] SPE-2 | 机检补齐 | 证据：\n",
        encoding="utf-8",
    )
    # 熔断回执（不带 handoff_prompt）→ 走 --print-relay 的实时生成降级路径，
    # 与 test-relay-clarity / test-relay-multi-task 的夹具口径一致。
    (flow / "budget" / "20260925-120000-stop.json").write_text(
        json.dumps(
            {"operation": "budget_stop", "thread_id": SRC_THREAD, "input_tokens": 300_000},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    sessions = root / "sessions" / "2026" / "09" / "25"
    sessions.mkdir(parents=True)
    (sessions / f"rollout-2026-09-25T10-00-00-{NEW_THREAD}.jsonl").write_text(
        json.dumps(
            {
                "type": "event_msg",
                "payload": {"type": "task_complete", "last_agent_message": "已交付，见看板。"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return flow


def relay(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(BUDGET),
            "--print-relay",
            "--project",
            str(root),
            "--thread-id",
            NEW_THREAD,
            "--intent",
            "接手上一会话的交接",
            "--sessions-root",
            str(root / "sessions"),
            *extra,
        ],
        text=True,
        capture_output=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build(root)
        result = relay(root)
        text = result.stdout
        assert result.returncode == 0, (result.returncode, result.stderr)

        # SPE-1：交接来源三件套（源 thread id / 源任务卡 / 源交接棒标题）。
        assert SRC_THREAD in text, text[:1500]
        assert TICKET in text, text[:1500]
        assert "交接棒" in text, text[:1500]

        # SPE-2：一句话说清「这是什么 + 当前状态」。
        assert "任务说明" in text, text[:2000]
        assert "把 X 收口" in text, text[:2000]
        assert "已推送" in text or "现状" in text, text[:2000]

        # SPE-3：下一步（第一件事 + 验收标准 + 未回收规格点数）。
        assert "下一步" in text, text[:2500]
        assert "run-all.sh" in text, text[:2500]
        assert "未回收" in text, text[:2500]

        # SPE-4：卡在 [-] 待验收区也要解析出 ticket（不再恒为「未指定」）。
        assert "未指定" not in text.split("任务说明")[0], text[:1500]

        # 反向：活跃区与待验收区都没有该卡时，仍应明确说「未指定」并给候选，而不是编造。
        (root / "flow" / "plan.md").write_text(
            "# Plan\n## 🎯 当前聚焦待办 (P0)\n- 无\n", encoding="utf-8"
        )
        empty = relay(root).stdout
        assert "未指定" in empty, empty[:1200]
    print("PASS: relay prompt carries source identity, task summary and next step")


if __name__ == "__main__":
    main()
