#!/usr/bin/env python3
"""接力提示词必须指名「本次要接的那张卡」，而不是猜顶部交接棒那一张。

事故形态（2026-09-24，zhengjie-hrm 主仓 13 张并行卡 + 3 个 worktree）：
  1) 顶部交接棒常是 A 卡，而本轮要接力的是 B 卡 → 提示词把新会话指向 A 卡；
  2) 顶部那张卡刚被归档 → 提示词给出 `flow/tasks/<已归档>.md` 这种**不存在的路径**；
  3) 分端在 worktree 跑、主仓做共享合并 → 提示词不写工作根，新会话在主仓开工；
  4) 并行队列与 `[!]` 阻塞项完全不体现 → 新会话既不知道有哪些卡在跑，也不知道哪张卡在等外部解除。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET = ROOT / "scripts" / "flow-budget.py"
UID = "01a0c1cd-a264-7321-8779-8440e6de59ac"
CARD_A = "W2-PARALLEL-20260922"
CARD_B = "W2-P4-CANDIDATE-H5-20260922"
CARD_C = "W2-P6-ENTERPRISE-MOBILE-20260922"
ARCHIVED = "PFP-RELAY-CLARITY-20260924"


def build(root: Path) -> Path:
    flow = root / "flow"
    for name in ("tasks", "specs", "budget", "history/tasks", "gc/receipts", "规范"):
        (flow / name).mkdir(parents=True, exist_ok=True)
    (flow / "规范" / "VERSION").write_text(
        (ROOT / "VERSION").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (flow / "plan.md").write_text(
        "\n".join(
            [
                "# Plan",
                "## 🎯 当前聚焦待办 (P0)",
                f"- [ ] {CARD_A} [P0] 总控：并行调度 P4/P6 两路",
                f"- [ ] {CARD_B} [P0] 求职者 H5 25 行矩阵收口",
                f"- [ ] {CARD_C} [P0] 企业移动端收尾（M4 前置）",
                "- [!] W2-MERGE-WINDOW-20260923 [P1] 合并窗口：等 P4(1)+P6 未提交成果",
                "## ⏳ 待人工验收 (Pending Verification)",
                "- [-] W2-ADMIN-HOME-DESIGN-BUG-20260923 [P0] 等人工验收",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for name in ("charter.md", "decisions.md", "踩坑记录.md"):
        (flow / name).write_text("", encoding="utf-8")
    # 顶部交接棒属于 A 卡；B 卡才是本轮要接的活；ARCHIVED 卡只在 history/ 里。
    (flow / "进展.md").write_text(
        "\n".join(
            [
                f"## 2026-09-24 · {CARD_A} · 交接棒（SDD 蒸馏） · thread={UID}",
                "- 来源会话：thread=" + UID,
                "- 规格点(SPE)：SPE-1 调度",
                "- 待办(TODO)：- [ ] SPE-1",
                "- 现状：调度中",
                "- 还剩：SPE-1",
                "- 卡在哪：无",
                "- 下一步：按卡施工",
                f"- 台账：flow/specs/{CARD_A}.md",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for ticket in (CARD_A, CARD_B, CARD_C):
        (flow / "tasks" / f"{ticket}.md").write_text(
            "\n".join(
                [
                    f"ticket_id: {ticket}",
                    "objective: 占位目标",
                    "mode: execute",
                    "method: SDD,TDD",
                    "scope: 输入=x；输出=y；边界=z",
                    "write_whitelist: src/**",
                    "verify_command: python3 -c 'print(1)'",
                    "acceptance: Given x，When y，Then z",
                ]
            ),
            encoding="utf-8",
        )
    (flow / "history" / "tasks" / f"{ARCHIVED}.md").write_text(
        f"ticket_id: {ARCHIVED}\nmode: execute\n", encoding="utf-8"
    )
    return flow


def relay(root: Path, intent: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(BUDGET),
            "--print-relay",
            "--project",
            str(root),
            "--thread-id",
            UID,
            "--intent",
            intent,
            "--sessions-root",
            str(root / "sessions"),
            *extra,
        ],
        text=True,
        capture_output=True,
    )


def write_session(path: Path, tokens: int, window: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "task_started",
                    "turn_id": f"{path.stem}-turn-0",
                    "model_context_window": window,
                },
            },
            ensure_ascii=False,
        )
        + "\n"
        + json.dumps(
            {
                "type": "token_usage_record",
                "payload": {
                    "turn_token_usage": {
                        "input_tokens": tokens,
                        "cached_input_tokens": 0,
                        "output_tokens": 10,
                        "total_tokens": tokens + 10,
                    },
                    "thread_token_usage": {"input_tokens": tokens, "cached_input_tokens": 0},
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        flow = build(root)
        write_session(root / "sessions" / "2026" / "09" / "24" / f"rollout-{UID}.jsonl", 300_000, 950_000)
        # 老回执（无 handoff_prompt）→ 走实时生成降级路径
        (flow / "budget" / "20260924-070000-stop.json").write_text(
            json.dumps({"operation": "budget_stop", "thread_id": UID}, ensure_ascii=False),
            encoding="utf-8",
        )

        # SPE-1 反面：顶部交接棒是 A 卡，但本轮意图是「P4 求职者 H5」→ 必须指向 B 卡。
        doc = relay(root, f"{CARD_B} 求职者 H5 矩阵收口")
        text = doc.stdout
        assert doc.returncode == 0, (doc.returncode, doc.stderr)
        assert f"flow/tasks/{CARD_B}.md" in text, text[-1500:]
        assert f"flow/tasks/{CARD_A}.md" not in text, text[-1500:]

        # SPE-1 正面：显式 --ticket 优先于意图匹配与顶部交接棒。
        explicit = relay(root, "随便的意图", "--ticket", CARD_C)
        assert f"flow/tasks/{CARD_C}.md" in explicit.stdout, explicit.stdout[-1200:]

        # SPE-2：卡已归档（只在 history/）→ 不得给出 tasks/<死卡>，改为列活跃区候选。
        gone = relay(root, f"{ARCHIVED} 继续做")
        assert f"flow/tasks/{ARCHIVED}.md" not in gone.stdout, gone.stdout[-1200:]
        assert "活跃区" in gone.stdout or "候选" in gone.stdout, gone.stdout[-1200:]

        # SPE-3：并行队列与阻塞项必须出现，且声明分端/主仓分工。
        assert CARD_B in text and CARD_C in text, text[-1500:]
        assert "[!]" in text or "阻塞" in text, text[-1500:]
        assert "worktree" in text or "工作根" in text, text[-1500:]
    print("PASS: relay prompt names the right card and shows the parallel queue")


if __name__ == "__main__":
    main()
