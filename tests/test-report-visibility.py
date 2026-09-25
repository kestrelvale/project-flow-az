#!/usr/bin/env python3
"""收工看板/汇报必须真实、完整、可被点名：修渲染矛盾与截断，并对「漏贴看板」加机检。

现场（2026-09-24/25，zhengjie-hrm）：
  1) `flow-deliver.py` 归档分区把 plan.md 的占位文字原样带出
     → 看板写「- 无（flow/history/tasks/ 已归档 82 张任务卡）」，前半句是「无」、
       后半句说 82 张，用户读到「看板宕机了」；
  2) 决策分区把 decisions.md 里多行条目的续行当独立条目输出
     → 出现半截 `- 决策:` / ``- `resolve_`` 这种残句；
  3) 会话漏贴看板没有任何机检：`flow-boot.py` 只查「查无交付回执」，
     不查「回执有、但回复里没贴看板」，于是漏贴无声无息。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DELIVER = ROOT / "scripts" / "flow-deliver.py"
BUDGET = ROOT / "scripts" / "flow-budget.py"
BOOT = ROOT / "scripts" / "flow-boot.py"
UID = "01a0cf2d-89f3-7ae1-a981-51662657ac2e"
TICKET = "T1-BOARD-20260925"


def build(root: Path) -> tuple[Path, Path]:
    flow = root / "flow"
    for name in ("tasks", "specs", "budget", "deliveries", "gc/receipts", "history/tasks", "规范"):
        (flow / name).mkdir(parents=True, exist_ok=True)
    (flow / "规范" / "VERSION").write_text(
        (ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (flow / "plan.md").write_text(
        "\n".join(
            [
                "# Plan",
                "## 🎯 当前聚焦待办 (P0)",
                f"- [ ] {TICKET} [P0] 看板渲染修复",
                "## ⏳ 待人工验收 (Pending Verification)",
                "- 无",
                "## 📦 已完结归档 (Archived in flow/history/)",
                "- 无（本条在验收通过后移入 `flow/history/tasks/`）",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for name in ("charter.md", "踩坑记录.md"):
        (flow / name).write_text("", encoding="utf-8")
    # 决策流水：第一条是多行条目（续行不含标记），第二条正常。
    (flow / "decisions.md").write_text(
        "\n".join(
            [
                "# decisions",
                "- [⚡ 自动决策] 统一登录夹具：",
                "  `resolve_feedback` MCP 工具与 `/api/feedback/resolve` 自适应回写。",
                "- [⚠️ 人工决策门] 订单状态冻结为 50/60/70。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    # 历史归档 3 张：必须走 flow-gc.py --task-archive（否则缺 JSON 回执，flow-boot 会拦）
    for index in range(3):
        ticket = f"OLD-{index}"
        (flow / "tasks" / f"{ticket}.md").write_text(
            f"ticket_id: {ticket}\nmode: execute\n", encoding="utf-8"
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "flow-gc.py"),
                str(root),
                "--task-archive",
                ticket,
                "--reason",
                "user_accepted",
                "--evidence",
                "fixture：看板归档计数用",
                "--apply",
            ],
            text=True,
            capture_output=True,
        )
    (flow / "tasks" / f"{TICKET}.md").write_text(
        "\n".join(
            [
                f"ticket_id: {TICKET}",
                "objective: 看板渲染修复",
                "mode: execute",
                "method: SDD,TDD,ATDD,BDD",
                "scope: 输入=x；输出=y；边界=z",
                "write_whitelist: scripts/flow-deliver.py",
                "verify_command: python3 tests/test-report-visibility.py",
                "acceptance: Given x，When y，Then z",
                f"spec_ledger: flow/specs/{TICKET}.md",
            ]
        ),
        encoding="utf-8",
    )
    (flow / "specs" / f"{TICKET}.md").write_text(
        "- [x] SPE-1 | 看板 | 证据：tests/test-report-visibility.py\n", encoding="utf-8"
    )
    (flow / "进展.md").write_text(
        f"## 2026-09-25 · {TICKET} · 交接棒（SDD 蒸馏） · thread={UID}\n"
        "- 来源会话：thread=" + UID + "\n"
        "- 规格点(SPE)：SPE-1\n- 待办(TODO)：- [x] SPE-1\n- 现状：x\n- 还剩：无\n"
        "- 卡在哪：无\n- 下一步：x\n"
        f"- 台账：flow/specs/{TICKET}.md\n",
        encoding="utf-8",
    )
    sessions = root / "sessions" / "2026" / "09" / "25"
    sessions.mkdir(parents=True)
    return flow, sessions


def write_session(path: Path, reply: str) -> None:
    # 必须写 `task_complete.last_agent_message`：机检（relay/board）只认这一条，
    # 它才是「那一轮对外回复」的唯一可靠依据（与 flow-budget.last_visible_reply 对齐）。
    path.write_text(
        json.dumps(
            {
                "type": "event_msg",
                "payload": {"type": "task_complete", "last_agent_message": reply},
            },
            ensure_ascii=False,
        )
        + "\n"
        + json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "task_started",
                    "turn_id": f"{path.stem}-turn-0",
                    "model_context_window": 950_000,
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def deliver(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(DELIVER),
            str(root / "flow" / "tasks" / f"{TICKET}.md"),
            "--changed",
            "x",
            "--evidence",
            "python3 tests/test-report-visibility.py Exit 0",
            "--what",
            "w",
            "--why",
            "y",
            "--understanding",
            "u",
            "--outputs",
            "o",
            "--next-step",
            "n",
        ],
        text=True,
        capture_output=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flow, sessions = build(root)

        # SPE-1：归档分区必须给真实计数，不能输出与事实矛盾的「- 无」。
        board = deliver(root)
        assert board.returncode == 0, (board.returncode, board.stderr)
        text = board.stdout
        assert "## 📦 已完结归档 (Archived in flow/history/)" in text, text[:800]
        archived_section = text.split("## 📦 已完结归档 (Archived in flow/history/)", 1)[1].split(
            "## 💡", 1
        )[0]
        assert "已归档 3 张" in archived_section, archived_section
        assert "OLD-0" in archived_section, archived_section
        assert archived_section.strip().splitlines()[0].strip() != "- 无", archived_section

        # SPE-2：决策分区只输出完整条目，不得留半截续行。
        decisions = text.split("## 💡 本轮决策记录 (Decisions)", 1)[1]
        for line in decisions.splitlines():
            if not line.strip():
                continue
            assert not line.strip().startswith("`resolve_"), decisions
            assert line.strip() != "- [⚡ 自动决策] 统一登录夹具：", decisions
        assert "订单状态冻结" in decisions, decisions

        # SPE-3：上一轮回复漏贴看板 → 下一轮开工必须点名。
        write_session(sessions / f"rollout-2026-09-25T10-00-00-{UID}.jsonl", "本轮只写了一句结论，没有贴看板。")
        missing = subprocess.run(
            [
                sys.executable,
                str(BUDGET),
                "--project",
                str(root),
                "--thread-id",
                UID,
                "--intent",
                f"{TICKET} 继续",
                "--sessions-root",
                str(root / "sessions"),
                "--read-only",
            ],
            text=True,
            capture_output=True,
        )
        assert "上轮回复缺失任务看板" in missing.stdout, missing.stdout[-1200:]

        boot = subprocess.run(
            [
                sys.executable,
                str(BOOT),
                str(root),
                "--intent",
                f"{TICKET} 继续",
                "--thread-id",
                UID,
                "--sessions-root",
                str(root / "sessions"),
            ],
            text=True,
            capture_output=True,
        )
        assert "上轮回复缺失任务看板" in boot.stdout, boot.stdout[-1500:]

        # 反向：贴了看板的回复不得被点名。
        write_session(
            sessions / f"rollout-2026-09-25T10-00-00-{UID}.jsonl",
            "### 📊 任务状态看板\n\n## 🎯 当前聚焦待办 (P0)\n- 无\n",
        )
        ok = subprocess.run(
            [
                sys.executable,
                str(BOOT),
                str(root),
                "--intent",
                f"{TICKET} 继续",
                "--thread-id",
                UID,
                "--sessions-root",
                str(root / "sessions"),
            ],
            text=True,
            capture_output=True,
        )
        assert "上轮回复缺失任务看板" not in ok.stdout, ok.stdout[-1500:]
    print("PASS: board lists real archives, decisions stay whole, missing board is called out")


if __name__ == "__main__":
    main()
